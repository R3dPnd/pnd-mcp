"""integrations.job_search.hunt — the overnight hunt end to end, with fakes
for the app, Claude and the link checker."""

import json

import pytest

from integrations.job_search.client import JobSearchUnavailable
from integrations.job_search.hunt import build_queries, run_hunt
from integrations.job_search.leads import LeadStore
from shared.claude_cli import ClaudeResult

TODAY = "2026-11-05"
CFG = {
    "user": {"location": "Tacoma, WA"},
    "job_hunt": {
        "pay_floor_hourly": 25, "max_leads": 8, "max_queries": 6,
        "locations": ["Remote", "Tacoma, WA", "Seattle, WA"],
        "kinds": ["part-time SWE", "AI code evaluation/training", "freelance", "code review", "bounties"],
        "schedule": "Async first. Mon-Thu commuting Tacoma->Seattle. Fridays flexible.",
        "exclude": ["on-call", "full-time"],
    },
}


def posting(pid, title="Part-time SWE", company="Acme", salary=None, period=None, url=None):
    return {"id": pid, "title": title, "company": company, "location": "Remote", "is_remote": True,
            "description": "Build things.", "url": url or f"https://jobs.example/{pid}",
            "salary_min": salary, "salary_max": salary, "salary_period": period, "salary_currency": "USD"}


class FakeApp:
    def __init__(self, postings=(), error=None):
        self.postings, self.error, self.queries = list(postings), error, []

    def search(self, query, location="", remote=False):
        self.queries.append((query, location, remote))
        if self.error:
            raise self.error
        return list(self.postings)

    def active_resume_text(self):
        if self.error and "not reachable" in str(self.error):
            raise self.error
        return "Preston Harms — Software Engineer, 8 years, Go/Python/TypeScript"


def fake_claude(screens=None, gigs=(), screen_text=None):
    def claude(prompt, allowed_tools=None, timeout=120):
        if allowed_tools:  # the gig web search
            return ClaudeResult(ok=True, text=json.dumps(list(gigs)), error="")
        if screen_text is not None:
            return ClaudeResult(ok=True, text=screen_text, error="")
        keys = [line.split('"key": "')[1].split('"')[0] for line in prompt.splitlines() if '"key": "' in line]
        items = [{"key": k, "keep": True, "score": (screens or {}).get(k, 50), "fit": f"fit {k}",
                  "suggestion": f"tip {k}"} for k in keys if (screens or {}).get(k, 50) is not None]
        return ClaudeResult(ok=True, text=json.dumps(items), error="")
    return claude


def hunt(tmp_path, app, claude, status=lambda url: 200, today=TODAY):
    return run_hunt(CFG, app=app, store=LeadStore(tmp_path / "leads.json"), claude=claude,
                    get_status=status, today=today, reports_dir=tmp_path / "reports")


GIG = {"title": "Code evaluator", "org": "DataAnnotation", "url": "https://www.dataannotation.tech/", "pay": "$40/h"}


def test_hunt_writes_a_ranked_report_with_links_and_fit_lines(tmp_path):
    app = FakeApp([posting("p1"), posting("p2"), posting("p3")])
    result = hunt(tmp_path, app, fake_claude({"app:p1": 50, "app:p2": 90, "app:p3": 70}, gigs=[GIG]))
    report = result.report_path.read_text()
    assert result.report_path == tmp_path / "reports" / f"{TODAY}.md"
    order = [report.index(f"jobs.example/{p}") for p in ("p2", "p3", "p1")]
    assert order == sorted(order)  # ranked by score
    assert "## 1. Part-time SWE — Acme" in report
    assert "Fit: fit app:p2" in report and "Suggestion: tip app:p2" in report
    assert "[gig]" in report and "dataannotation.tech" in report
    assert "delivered_at:" in report


def test_second_hunt_has_no_repeats(tmp_path):
    app = FakeApp([posting("p1")])
    hunt(tmp_path, app, fake_claude())
    second = hunt(tmp_path, app, fake_claude(), today="2026-11-06")
    assert second.added == []
    assert "No new leads" in second.report_path.read_text()


def test_duplicate_posting_across_queries_appears_once(tmp_path):
    result = hunt(tmp_path, FakeApp([posting("p1")]), fake_claude())  # every query returns p1
    assert [l.key for l in result.added] == ["app:p1"]


def test_missing_jsearch_key_is_noted_and_gigs_still_come_through(tmp_path):
    app = FakeApp(error=JobSearchUnavailable("job search is not configured: set JOBS_API_KEY"))
    result = hunt(tmp_path, app, fake_claude(gigs=[GIG]))
    report = result.report_path.read_text()
    assert report.count("set JOBS_API_KEY") == 1  # noted once, not per query
    assert [l.kind for l in result.added] == ["gig"]


def test_app_down_is_noted_and_exit_path_is_clean(tmp_path):
    app = FakeApp(error=JobSearchUnavailable("job search app not reachable at http://localhost:8080/api/v1"))
    result = hunt(tmp_path, app, fake_claude(gigs=[GIG]))
    assert "not reachable" in result.report_path.read_text()
    assert len(result.added) == 1


def test_unparseable_screen_keeps_candidates_unscored_with_a_note(tmp_path):
    result = hunt(tmp_path, FakeApp([posting("p1"), posting("p2")]), fake_claude(screen_text="I can't help with that."))
    report = result.report_path.read_text()
    assert len(result.added) == 2 and all(l.score == 0 for l in result.added)
    assert "not screened" in report.lower()


def test_dead_links_dropped_and_blocked_links_flagged(tmp_path):
    app = FakeApp([posting("ok"), posting("dead"), posting("blocked")])
    status = {"https://jobs.example/ok": 200, "https://jobs.example/dead": 404, "https://jobs.example/blocked": 403}
    result = hunt(tmp_path, app, fake_claude(), status=lambda url: status[url])
    report = result.report_path.read_text()
    assert {l.key for l in result.added} == {"app:ok", "app:blocked"}
    assert "couldn't verify" in report and "jobs.example/dead" not in report


def test_stated_pay_below_floor_dropped_unknown_pay_kept(tmp_path):
    app = FakeApp([posting("low", salary=40000, period="YEAR"), posting("high", salary=90000, period="YEAR"),
                   posting("unknown")])
    result = hunt(tmp_path, app, fake_claude())
    assert {l.key for l in result.added} == {"app:high", "app:unknown"}
    assert "pay not listed" in result.report_path.read_text()


def test_midday_rerun_appends_and_continues_numbering(tmp_path):
    hunt(tmp_path, FakeApp([posting("p1"), posting("p2")]), fake_claude())
    path = tmp_path / "reports" / f"{TODAY}.md"
    path.write_text(path.read_text().replace("delivered_at:", "delivered_at: 2026-11-05T07:01:00"))
    again = hunt(tmp_path, FakeApp([posting("p3")]), fake_claude())
    report = again.report_path.read_text()
    assert [l.number for l in again.added] == [3]
    assert "## 1." in report and "## 3." in report
    assert "delivered_at: 2026-11-05T07:01:00" in report


def test_build_queries_pairs_kinds_with_locations_and_caps():
    queries = build_queries(CFG["job_hunt"], cap=6)
    assert ("part-time SWE", "", True) in queries
    assert ("part-time SWE", "Tacoma, WA", False) in queries
    assert all("evaluation" not in q and "bounties" not in q and "code review" not in q for q, _, _ in queries)
    assert len(queries) == 6
    assert len(build_queries(CFG["job_hunt"], cap=2)) == 2


def test_main_rejects_unknown_commands(capsys):
    from integrations.job_search.__main__ import main

    assert main(["nope"]) == 2
    assert "usage" in capsys.readouterr().err


def test_main_runs_a_hunt_with_the_persona_data_dir(tmp_path, monkeypatch, capsys):
    import integrations.job_search.__main__ as entry
    from integrations.job_search.hunt import HuntResult

    seen = {}
    monkeypatch.setattr(entry, "load_config", lambda: {"job_search": {"base_url": "http://app/api/v1"}})
    monkeypatch.setattr(entry, "data_dir", lambda: tmp_path)
    monkeypatch.setattr(entry, "run_hunt", lambda cfg, **kw: seen.update(kw) or
                        HuntResult(report_path=tmp_path / "r.md", added=[], notes=["set JOBS_API_KEY"]))
    assert entry.main(["hunt"]) == 0
    assert seen["app"].base_url == "http://app/api/v1"
    assert seen["store"].path == tmp_path / "applications" / "leads.json"
    assert seen["reports_dir"] == tmp_path / "applications" / "reports"
    assert "note: set JOBS_API_KEY" in capsys.readouterr().out


def test_app_down_with_varying_errors_gives_one_note(tmp_path):
    class Down(FakeApp):
        def search(self, query, location="", remote=False):
            raise JobSearchUnavailable("job search app not reachable at http://localhost:8080/api/v1")

        def active_resume_text(self):
            raise JobSearchUnavailable("job search app not reachable at http://localhost:8080/api/v1")

    report = hunt(tmp_path, Down(), fake_claude(gigs=[GIG])).report_path.read_text()
    assert report.count("not reachable") == 1


def test_gig_search_is_told_every_known_gig_url_not_just_todays(tmp_path):
    prompts = []

    def claude(prompt, allowed_tools=None, timeout=120):
        if allowed_tools:
            prompts.append(prompt)
            return ClaudeResult(ok=True, text=json.dumps([GIG]), error="")
        return fake_claude()(prompt, allowed_tools, timeout)

    hunt(tmp_path, FakeApp(), claude)
    hunt(tmp_path, FakeApp(), claude, today="2026-11-06")
    assert "https://www.dataannotation.tech/" in prompts[1]


def test_gig_reply_without_a_list_is_noted(tmp_path):
    def claude(prompt, allowed_tools=None, timeout=120):
        if allowed_tools:
            return ClaudeResult(ok=True, text="Sorry, I couldn't search right now.", error="")
        return fake_claude()(prompt, allowed_tools, timeout)

    report = hunt(tmp_path, FakeApp([posting("p1")]), claude).report_path.read_text()
    assert "gig search" in report.lower() and "no gig leads" in report.lower()


def test_screen_with_no_matching_keys_falls_back_to_unscored_with_a_note(tmp_path):
    mangled = json.dumps([{"key": "app:p", "keep": True, "score": 90, "fit": "f", "suggestion": "s"}])
    result = hunt(tmp_path, FakeApp([posting("p1"), posting("p2")]), fake_claude(screen_text=mangled))
    report = result.report_path.read_text()
    assert len(result.added) == 2
    assert "not screened" in report.lower()
