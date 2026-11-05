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
    """Same posting, same key: lowercase scheme/host, no fragment, no utm_* params."""
    parts = urlsplit(url.strip())
    query = urlencode([(k, v) for k, v in parse_qsl(parts.query) if not k.lower().startswith("utm_")])
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, query, ""))


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

    def add(self, leads: list[Lead], report_date: str) -> list[Lead]:
        known = self.known_keys()
        number = max((l.number for l in self._leads if l.report_date == report_date), default=0)
        added = []
        for lead in leads:
            if lead.key in known:
                continue
            number += 1
            lead.number, lead.report_date = number, report_date
            known.add(lead.key)
            added.append(lead)
        self._leads += added
        self._save()
        return added

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
