"""The overnight job hunt (akane's job-hunt design §7.3): JSearch postings via
pnd-job-search, plus a Claude web search for async gig work, screened in one
Claude call against the user's resume and constraints, filtered by rules in
code (pay floor, dead links), numbered, and written as the morning report.

A hunt never fails silently: anything that went wrong (app down, no JSearch
key, Claude unavailable) becomes a note at the top of the report.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from integrations.job_search.client import JobSearchApp, JobSearchUnavailable
from integrations.job_search.leads import Lead, LeadStore, normalize_url
from integrations.job_search.report import delivered_at, render_report
from integrations.job_search.rules import below_pay_floor, check_link
from integrations.job_search.screening import gig_prompt, parse_gigs, parse_screen, screen_prompt
from shared.claude_cli import ClaudeResult

DEFAULTS = {"pay_floor_hourly": 25, "max_leads": 8, "max_queries": 6, "locations": ["Remote"], "kinds": [],
            "schedule": "", "exclude": []}
# Kinds JSearch's job boards don't carry; the Claude gig search covers them.
_GIG_MARKERS = ("ai code", "evaluation", "training", "bount", "code review", "gig")
_SCREEN_TIMEOUT = 600
_GIG_TIMEOUT = 600


@dataclass
class HuntResult:
    report_path: Path
    added: list[Lead]
    notes: list[str] = field(default_factory=list)


def _is_gig_kind(kind: str) -> bool:
    return any(m in kind.lower() for m in _GIG_MARKERS)


def build_queries(criteria: dict[str, Any], cap: int) -> list[tuple[str, str, bool]]:
    queries = []
    for kind in criteria.get("kinds") or []:
        if _is_gig_kind(kind):
            continue
        for loc in criteria.get("locations") or ["Remote"]:
            queries.append((kind, "", True) if loc.lower() == "remote" else (kind, loc, False))
    return queries[:cap]


def _pay(p: dict) -> str:
    lo, hi, period = p.get("salary_min"), p.get("salary_max"), (p.get("salary_period") or "").lower()
    if lo is None and hi is None:
        return ""
    amounts = sorted({a for a in (lo, hi) if a is not None})
    return "–".join(f"${a:,.0f}" for a in amounts) + (f" per {period}" if period else "")


def _posting_candidate(p: dict) -> dict:
    return {"key": f"app:{p['id']}", "title": p.get("title", ""), "org": p.get("company", ""),
            "url": p.get("url") or "", "pay": _pay(p), "location": p.get("location") or "",
            "remote": bool(p.get("is_remote")), "kind": "job", "description": p.get("description") or "",
            "_salary": (p.get("salary_min"), p.get("salary_max"), p.get("salary_period"))}


def _gig_candidate(g: dict) -> dict:
    return {"key": "url:" + normalize_url(g["url"]), "title": g.get("title", ""), "org": g.get("org", ""),
            "url": g["url"], "pay": g.get("pay", ""), "location": "", "remote": True, "kind": "gig",
            "description": "", "_salary": (None, None, None)}


def run_hunt(cfg: dict[str, Any], *, app: JobSearchApp, store: LeadStore,
             claude: Callable[..., ClaudeResult], get_status: Callable[[str], int],
             today: str, reports_dir: Path) -> HuntResult:
    criteria = {**DEFAULTS, **(cfg.get("job_hunt") or {})}
    location = (cfg.get("user") or {}).get("location", "")
    notes: list[str] = []

    def note(message: str) -> None:
        if message not in notes:
            notes.append(message)

    known = store.known_keys()
    candidates: dict[str, dict] = {}

    try:
        resume = app.active_resume_text()
    except JobSearchUnavailable as e:
        resume = ""
        note(str(e))
    for query, loc, remote in build_queries(criteria, criteria["max_queries"]):
        try:
            for p in app.search(query, loc, remote):
                c = _posting_candidate(p)
                if c["key"] not in known and c["url"]:
                    candidates.setdefault(c["key"], c)
        except JobSearchUnavailable as e:
            note(str(e))

    if any(_is_gig_kind(k) for k in criteria["kinds"]):
        known_urls = [l.url for l in store.for_date(today)] + [c["url"] for c in candidates.values()]
        gig = claude(gig_prompt(criteria, location, resume[:600], known_urls),
                     allowed_tools=["WebSearch", "WebFetch"], timeout=_GIG_TIMEOUT)
        if gig.ok:
            for g in parse_gigs(gig.text):
                c = _gig_candidate(g)
                if c["key"] not in known:
                    candidates.setdefault(c["key"], c)
        else:
            note(f"Gig search didn't run: {gig.error}")

    floor = criteria["pay_floor_hourly"]
    pool = [c for c in candidates.values() if not below_pay_floor(*c["_salary"], floor)]

    screened: list[tuple[dict, int, str, str]] = []
    if pool:
        reply = claude(screen_prompt(pool, resume, criteria, location), timeout=_SCREEN_TIMEOUT)
        try:
            if not reply.ok:
                raise ValueError(reply.error)
            screens = parse_screen(reply.text)
            screened = [(c, s.score, s.fit, s.suggestion) for c in pool
                        if (s := screens.get(c["key"])) is not None and s.keep]
        except ValueError as e:
            note(f"Couldn't screen tonight's postings ({e}); they're listed unscored, not screened against your criteria.")
            screened = [(c, 0, "not screened", "") for c in pool]

    leads = []
    for c, score, fit, suggestion in sorted(screened, key=lambda t: -t[1]):
        link = check_link(c["url"], get_status)
        if link == "dead":
            continue
        leads.append(Lead(key=c["key"], title=c["title"], org=c["org"], url=c["url"], pay=c["pay"],
                          location=c["location"], remote=c["remote"], kind=c["kind"], score=score,
                          fit=fit, suggestion=suggestion, link=link))
        if len(leads) == criteria["max_leads"]:
            break

    added = store.add(leads, today)
    report_path = reports_dir / f"{today}.md"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_report(today, store.for_date(today), notes, delivered_at(report_path)))
    return HuntResult(report_path=report_path, added=added, notes=notes)
