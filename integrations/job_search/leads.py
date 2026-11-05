"""Akane's record of every lead she has reported, so a lead is never shown as
new twice, and "number 3" maps to a lead in the latest report.

Stored as JSON at <data_dir>/applications/leads.json.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


@dataclass
class Lead:
    key: str          # "app:<posting id>" (JSearch via the app) or "url:<normalized url>" (gig search)
    title: str
    org: str
    url: str
    pay: str
    location: str
    remote: bool
    kind: str         # "job" | "gig"
    score: int
    fit: str
    suggestion: str
    link: str         # "ok" | "blocked"
    number: int = 0
    report_date: str = ""
    status: str = "new"  # new | shown | dismissed | applied | tailoring | tailored


def normalize_url(url: str) -> str:
    """Same page, same key: lowercase scheme/host, no leading www., no trailing
    slash (the root stays "/"), no fragment, no utm_* params. Web search
    returns the same page in all these forms."""
    parts = urlsplit(url.strip())
    host = parts.netloc.lower().removeprefix("www.")
    path = parts.path.rstrip("/") or "/"
    query = urlencode([(k, v) for k, v in parse_qsl(parts.query) if not k.lower().startswith("utm_")])
    return urlunsplit((parts.scheme.lower(), host, path, query, ""))


def fingerprints(key: str, url: str, title: str, org: str) -> set[str]:
    """Every identity a lead can be recognised by. JSearch can return the same
    job under a new job_id (so a new app posting id), so the URL and the
    title+company count too."""
    prints = {key}
    if url:
        prints.add("url:" + normalize_url(url))
    if title.strip() and org.strip():
        norm = lambda text: " ".join(text.lower().split())  # noqa: E731
        prints.add(f"job:{norm(title)}|{norm(org)}")
    return prints


class LeadStore:
    def __init__(self, path: Path):
        self.path = path
        self._leads: list[Lead] = []
        if path.is_file():
            self._leads = [Lead(**d) for d in json.loads(path.read_text() or "[]")]

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps([asdict(l) for l in self._leads], indent=2))
        os.replace(tmp, self.path)

    def known_keys(self) -> set[str]:
        return {l.key for l in self._leads}

    def known_fingerprints(self) -> set[str]:
        return {f for l in self._leads for f in fingerprints(l.key, l.url, l.title, l.org)}

    def add(self, leads: list[Lead], report_date: str) -> list[Lead]:
        known = self.known_fingerprints()
        number = max((l.number for l in self._leads if l.report_date == report_date), default=0)
        added = []
        for lead in leads:
            prints = fingerprints(lead.key, lead.url, lead.title, lead.org)
            if prints & known:
                continue
            number += 1
            lead.number, lead.report_date = number, report_date
            known |= prints
            added.append(lead)
        self._leads += added
        self._save()
        return added

    def urls(self, kind: str | None = None) -> list[str]:
        return [l.url for l in self._leads if kind is None or l.kind == kind]

    def for_date(self, report_date: str) -> list[Lead]:
        return sorted((l for l in self._leads if l.report_date == report_date), key=lambda l: l.number)

    def latest_report_date(self) -> str | None:
        return max((l.report_date for l in self._leads), default=None)

    def by_number(self, n: int, report_date: str | None = None) -> Lead | None:
        date = report_date or self.latest_report_date()
        return next((l for l in self._leads if l.report_date == date and l.number == n), None)

    def set_status(self, key: str, status: str) -> None:
        for lead in self._leads:
            if lead.key == key:
                lead.status = status
        self._save()
