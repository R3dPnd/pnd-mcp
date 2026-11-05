"""What Akane says and shows about job hunting, and when it's due — the
morning report once a day, plus announcements from hunts that finished while
she was down. Pure file logic; app/services/morning_report_service.py
decides *when* to call `due` and actually speaks and posts.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from integrations.job_search.leads import Lead, LeadStore
from integrations.job_search.report import delivered_at, mark_delivered, render_report

_URL = re.compile(r"https?://\S+")


@dataclass
class Delivery:
    spoken: list[str] = field(default_factory=list)
    chat: list[str] = field(default_factory=list)


def pending_path(data_dir: Path) -> Path:
    return data_dir / "applications" / "pending_announcements.json"


def _short_title(title: str) -> str:
    short = re.split(r" - | \(|;", title, maxsplit=1)[0].strip()
    return short[:60].rstrip()


def _first_sentence(text: str) -> str:
    text = _URL.sub("", text)
    return re.split(r"(?<=[.!?])\s", text.strip(), maxsplit=1)[0].rstrip(" .:") + "."


def spoken_summary(leads: list[Lead], notes: list[str], opening: str = "Morning.", period: str = " overnight") -> str:
    """About three sentences, no URLs: how many leads, the best three, any problem."""
    if not leads:
        parts = [f"{opening} No new leads{period}."]
    else:
        count = f"{len(leads)} new lead{'s' if len(leads) != 1 else ''}{period}."
        top = [f"{l.org}'s {_short_title(l.title)}" + (f" at {l.pay}" if l.pay else "") for l in leads[:3]]
        label = {1: "It's", 2: "The best two:"}.get(len(top), "The best three:")
        best = top[0] if len(top) == 1 else "; ".join(top[:-1]) + f"; and {top[-1]}"
        parts = [opening, count, f"{label} {best}.", "They're in the chat."]
    if notes:
        parts.insert(-1 if leads else len(parts), f"One problem: {_first_sentence(notes[0])}")
    return " ".join(parts)


def report_notes(report_text: str) -> list[str]:
    return [line[2:] for line in report_text.splitlines() if line.startswith("> ")]


def chat_text(report_text: str) -> str:
    """The report without its front matter."""
    if report_text.startswith("---\n"):
        end = report_text.find("\n---\n", 4)
        if end != -1:
            return report_text[end + 5:].strip() + "\n"
    return report_text


def due(data_dir: Path, today: str, now: str) -> Delivery:
    """Everything owed to the user right now, marked as delivered: today's
    report if it hasn't been delivered, and any pending announcements."""
    out = Delivery()
    applications = data_dir / "applications"

    report = applications / "reports" / f"{today}.md"
    if report.is_file():
        # Go by lead status, not just delivered_at: leads an on-demand hunt
        # already announced are "shown" and mustn't be read again as
        # "overnight", and leads a later hunt appended after delivery are
        # "new" and still need reading.
        store = LeadStore(applications / "leads.json")
        leads = store.for_date(today)
        new = [l for l in leads if l.status == "new"]
        undelivered = not delivered_at(report)
        if new or (undelivered and not leads):
            notes = report_notes(report.read_text()) if undelivered else []
            out.spoken.append(spoken_summary(new, notes))
            out.chat.append(chat_text(render_report(today, new, notes)))
        if undelivered:
            mark_delivered(report, now)
        for lead in new:
            store.set_status(lead.key, "shown")

    pending = pending_path(data_dir)
    if pending.is_file():
        for item in json.loads(pending.read_text() or "[]"):
            if item.get("text"):
                out.spoken.append(item["text"])
            if item.get("chat"):
                out.chat.append(item["chat"])
        pending.unlink()
    return out
