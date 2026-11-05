"""integrations.job_search.delivery — what's due to be said and shown, once."""

import json

from integrations.job_search.delivery import Delivery, due, pending_path, spoken_summary
from integrations.job_search.leads import Lead, LeadStore
from integrations.job_search.report import render_report

TODAY = "2026-11-06"


def lead(n, org, title, pay="", key=None):
    return Lead(key=key or f"app:{n}", title=title, org=org, url=f"https://jobs.example/{n}", pay=pay,
                location="", remote=True, kind="job", score=90 - n, fit="f", suggestion="s", link="ok")


LEADS = [
    lead(1, "DataAnnotation", "Software Developer (part-time work from home) - AI Trainer", "$40–$125 per hour"),
    lead(2, "Meridial", "TypeScript Coding Specialist - Freelance AI Trainer Project", "$65/hr"),
    lead(3, "Handshake", "Remote Part-Time Software Engineer - AI Systems Reviewer"),
    lead(4, "Outlier", "Agentic AI Engineer; Freelance, Remote"),
]


def write_day(data_dir, date=TODAY, leads=LEADS, notes=()):
    store = LeadStore(data_dir / "applications" / "leads.json")
    added = store.add(list(leads), date)
    reports = data_dir / "applications" / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / f"{date}.md").write_text(render_report(date, added, list(notes)))
    return store


def test_spoken_summary_names_top_three_without_urls():
    text = spoken_summary(LEADS, [])
    assert text.startswith("Morning. 4 new leads overnight.")
    assert "DataAnnotation's Software Developer at $40–$125 per hour" in text
    assert "Meridial's TypeScript Coding Specialist at $65/hr" in text
    assert "Handshake's Remote Part-Time Software Engineer" in text
    assert "Outlier" not in text and "http" not in text
    assert text.endswith("They're in the chat.")


def test_spoken_summary_mentions_a_problem_note():
    text = spoken_summary(LEADS[:1], ["job search app not reachable at http://localhost:8080/api/v1. More."])
    assert "1 new lead overnight" in text
    assert "One problem:" in text and "http" not in text


def test_spoken_summary_with_no_leads():
    assert spoken_summary([], []) == "Morning. No new leads overnight."


def test_due_delivers_todays_report_once(tmp_path):
    write_day(tmp_path)
    first = due(tmp_path, TODAY, f"{TODAY}T07:30:00")
    assert len(first.spoken) == 1 and first.spoken[0].startswith("Morning.")
    assert len(first.chat) == 1 and "## 1." in first.chat[0] and "delivered_at" not in first.chat[0]
    assert "delivered_at: 2026-11-06T07:30:00" in (tmp_path / "applications/reports" / f"{TODAY}.md").read_text()
    assert due(tmp_path, TODAY, f"{TODAY}T08:00:00") == Delivery(spoken=[], chat=[])


def test_due_ignores_yesterdays_report(tmp_path):
    write_day(tmp_path, date="2026-11-05")
    assert due(tmp_path, TODAY, f"{TODAY}T07:30:00") == Delivery(spoken=[], chat=[])


def test_due_includes_and_clears_pending_announcements(tmp_path):
    pending = pending_path(tmp_path)
    pending.parent.mkdir(parents=True)
    pending.write_text(json.dumps([{"text": "Your job hunt is done.", "chat": "## 9. X — Y"}]))
    got = due(tmp_path, TODAY, f"{TODAY}T07:30:00")
    assert got.spoken == ["Your job hunt is done."] and got.chat == ["## 9. X — Y"]
    assert due(tmp_path, TODAY, f"{TODAY}T07:31:00") == Delivery(spoken=[], chat=[])


def test_due_marks_leads_shown(tmp_path):
    write_day(tmp_path)
    due(tmp_path, TODAY, f"{TODAY}T07:30:00")
    store = LeadStore(tmp_path / "applications" / "leads.json")
    assert {l.status for l in store.for_date(TODAY)} == {"shown"}
