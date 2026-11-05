"""integrations.servers.job_search_server — the router's job-hunt tools,
tested through their plain functions with a fake app."""

import pytest

from integrations.job_search.client import JobSearchUnavailable
from integrations.job_search.leads import Lead, LeadStore
from integrations.job_search.report import render_report
from integrations.servers import job_search_server as srv

TODAY = "2026-11-06"
STAGES = [{"id": f"s{i}", "name": n} for i, n in enumerate(
    ["Interested", "Ready to Apply", "Applied", "Phone Screen", "Technical Interview", "Final Round", "Offer", "Rejected"])]


class FakeApp:
    def __init__(self, applications=(), down=False):
        self.calls, self.applications, self.down = [], list(applications), down

    def _rec(self, *call):
        if self.down:
            raise JobSearchUnavailable("job search app not reachable at http://x")
        self.calls.append(call)

    def dismiss(self, pid): self._rec("dismiss", pid)
    def track(self, pid, applied): self._rec("track", pid, applied); return {"id": "a-" + pid, "current_stage_id": "s0"}
    def create_application(self, company, role, url, date_applied, source):
        self._rec("create", company, role, url, date_applied, source); return {"id": "a-gig", "current_stage_id": "s0"}
    def list_applications(self): self._rec("list"); return self.applications
    def stages(self, app_id): self._rec("stages", app_id); return STAGES
    def advance(self, app_id, stage_id): self._rec("advance", app_id, stage_id)
    def update_status(self, app_id, status): self._rec("status", app_id, status)


def lead(n, kind="job"):
    key = f"app:p{n}" if kind == "job" else f"url:https://gig.example/{n}"
    return Lead(key=key, title=f"Role {n}", org=f"Org{n}", url=f"https://gig.example/{n}", pay="$40/h",
                location="", remote=True, kind=kind, score=90, fit="fits", suggestion="tip", link="ok")


@pytest.fixture()
def store(tmp_path):
    s = LeadStore(tmp_path / "applications" / "leads.json")
    added = s.add([lead(1), lead(2), lead(3, kind="gig")], TODAY)
    reports = tmp_path / "applications" / "reports"
    reports.mkdir(parents=True)
    (reports / f"{TODAY}.md").write_text(render_report(TODAY, added, []))
    return s


def test_get_lead_reads_from_latest_report(store):
    text = srv.get_lead_text(store, 2)
    assert "Role 2" in text and "Org2" in text and "https://gig.example/2" in text and "fits" in text


def test_number_out_of_range_is_a_clear_answer(store):
    assert srv.get_lead_text(store, 9) == "There's no number 9 in the latest report (it has 3)."
    assert srv.dismiss(FakeApp(), store, 9) == "There's no number 9 in the latest report (it has 3)."


def test_dismiss_lead_marks_store_and_app(store):
    app = FakeApp()
    assert "Dismissed" in srv.dismiss(app, store, 1)
    assert ("dismiss", "p1") in app.calls and store.by_number(1).status == "dismissed"


def test_mark_applied_tracks_app_lead_and_advances_to_applied(store):
    app = FakeApp()
    srv.mark_applied(app, store, 2, TODAY)
    assert ("track", "p2", True) in app.calls and ("advance", "a-p2", "s2") in app.calls
    assert store.by_number(2).status == "applied"


def test_mark_applied_creates_application_for_gig(store):
    app = FakeApp()
    srv.mark_applied(app, store, 3, TODAY)
    assert ("create", "Org3", "Role 3", "https://gig.example/3", TODAY, "akane:gig") in app.calls


def apps(stage="s2"):
    return [{"id": "a1", "company": "Acme Corp", "current_stage_id": stage, "updated_at": "2026-11-01T00:00:00Z"}]


def test_update_application_interviewing_moves_to_next_interview_stage():
    app = FakeApp(apps(stage="s3"))  # at Phone Screen
    assert "Technical Interview" in srv.update_application(app, "acme", "interviewing")
    assert ("advance", "a1", "s4") in app.calls


def test_update_application_interviewing_from_applied_goes_to_phone_screen():
    app = FakeApp(apps(stage="s2"))
    srv.update_application(app, "Acme", "interviewing")
    assert ("advance", "a1", "s3") in app.calls


def test_update_application_rejected_sets_stage_and_status():
    app = FakeApp(apps())
    srv.update_application(app, "acme", "rejected")
    assert ("advance", "a1", "s7") in app.calls and ("status", "a1", "rejected") in app.calls


def test_update_application_closed_archives():
    app = FakeApp(apps())
    srv.update_application(app, "acme", "closed")
    assert ("status", "a1", "archived") in app.calls
    assert not any(c[0] == "advance" for c in app.calls)


def test_update_application_unknown_status_lists_choices():
    assert "applied, interviewing, offer, rejected, closed" in srv.update_application(FakeApp(apps()), "acme", "ghosted")


def test_update_application_unknown_company():
    assert "couldn't find" in srv.update_application(FakeApp(apps()), "Globex", "rejected").lower()


def test_update_application_picks_the_most_recent_of_several():
    two = apps() + [{"id": "a2", "company": "Acme Labs", "current_stage_id": "s2", "updated_at": "2026-11-05T00:00:00Z"}]
    app = FakeApp(two)
    text = srv.update_application(app, "acme", "offer")
    assert ("status", "a2", "offer") in app.calls and "Acme Labs" in text


def test_app_down_is_a_sentence_not_an_exception(store):
    assert "couldn't reach your job search app" in srv.dismiss(FakeApp(down=True), store, 1)


def test_get_morning_report_strips_front_matter(store, tmp_path):
    text = srv.morning_report_text(tmp_path)
    assert text.startswith("# Leads for") and "delivered_at" not in text


def test_get_morning_report_when_none(tmp_path):
    assert "find me jobs" in srv.morning_report_text(tmp_path)


def test_tools_are_registered_under_the_router_names():
    import asyncio

    names = {t.name for t in asyncio.run(srv.mcp.list_tools())}
    assert {"get_morning_report", "get_lead", "dismiss_lead", "mark_applied", "update_application"} <= names
