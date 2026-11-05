"""integrations.job_search.delivery — what's due to be said and shown, once."""

import dataclasses
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
    added = store.add([dataclasses.replace(l) for l in leads], date)  # copies: stores mutate leads
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


# ── On-demand hunts and the morning report (review I-1) ───────────────────────

def test_leads_already_announced_on_demand_are_not_read_again(tmp_path):
    # "find me jobs" created today's report and announced its leads (marked
    # shown) — the next trigger must not re-read them as "Morning… overnight".
    store = write_day(tmp_path)
    for l in store.for_date(TODAY):
        store.set_status(l.key, "shown")
    got = due(tmp_path, TODAY, f"{TODAY}T09:00:00")
    assert got.spoken == [] and got.chat == []
    assert "delivered_at: 2026-11-06T09:00:00" in (tmp_path / "applications/reports" / f"{TODAY}.md").read_text()


def test_pending_on_demand_announcement_is_the_only_thing_said(tmp_path):
    store = write_day(tmp_path, leads=LEADS[:1])
    for l in store.for_date(TODAY):
        store.set_status(l.key, "shown")  # the pending path marks them shown too
    pending = pending_path(tmp_path)
    pending.write_text(json.dumps([{"text": "Your job hunt is done. 1 new lead.", "chat": "## 1. …"}]))
    got = due(tmp_path, TODAY, f"{TODAY}T09:00:00")
    assert got.spoken == ["Your job hunt is done. 1 new lead."]


def test_leads_appended_after_delivery_are_still_read(tmp_path):
    # A nightly hunt that appends to an already-delivered report.
    store = write_day(tmp_path, leads=LEADS[:2])
    due(tmp_path, TODAY, f"{TODAY}T07:00:00")
    store = LeadStore(tmp_path / "applications" / "leads.json")
    store.add([dataclasses.replace(LEADS[2])], TODAY)
    got = due(tmp_path, TODAY, f"{TODAY}T09:00:00")
    assert len(got.spoken) == 1 and "Handshake" in got.spoken[0] and "DataAnnotation" not in got.spoken[0]
    assert "Handshake" in got.chat[0] and "DataAnnotation" not in got.chat[0]


def test_empty_report_is_still_read_once(tmp_path):
    write_day(tmp_path, leads=[], notes=["job search app not reachable at http://x"])
    got = due(tmp_path, TODAY, f"{TODAY}T07:00:00")
    assert got.spoken[0].startswith("Morning. No new leads overnight.") and "One problem" in got.spoken[0]
    assert due(tmp_path, TODAY, f"{TODAY}T08:00:00") == Delivery(spoken=[], chat=[])
