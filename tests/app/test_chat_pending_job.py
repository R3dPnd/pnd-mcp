"""A chat waiting on background work (think_deeply, a job hunt) says so —
the dashboard shows a working indicator until the result is posted."""

import time

from app.services import chat_service
from tests.app.test_announce import chat  # noqa: F401  (fixture)
from voice.event_bus import bus


def _send_with_tool(chat, stream_id, tool, monkeypatch):
    monkeypatch.setattr(chat_service, "get_shared_manager", lambda: type("M", (), {"tools": []})())

    def generate(text, on_tool=None, **kw):
        on_tool(tool)
        return "On it."

    monkeypatch.setattr(chat_service, "generate_response", generate)
    chat_service.send_message(stream_id, "do the thing")


def test_think_deeply_marks_the_chat_as_waiting_until_the_answer_arrives(chat, monkeypatch):
    stream = chat_service.create_stream("general", "plans")
    events = []
    listener = lambda t, p: events.append(t)
    bus.subscribe(listener)
    try:
        _send_with_tool(chat, stream["id"], "think_deeply", monkeypatch)
    finally:
        bus.unsubscribe(listener)
    pending = chat_service.get_stream(stream["id"])["pending_job"]
    assert pending["label"] == "Claude is working on it" and pending["started"] <= time.time()
    assert "chat.job" in events
    chat_service.post_to_stream(stream["id"], "## The plan")
    assert chat_service.get_stream(stream["id"]).get("pending_job") is None


def test_a_job_hunt_clears_when_the_hunt_posts_its_results(chat, monkeypatch):
    stream = chat_service.create_stream("general", "jobs")
    _send_with_tool(chat, stream["id"], "start_hunt", monkeypatch)
    assert chat_service.get_stream(stream["id"])["pending_job"]["label"] == "Job hunt running"
    chat_service.post_assistant_message("Morning report", "## 9. …")
    assert chat_service.get_stream(stream["id"]).get("pending_job") is None


def test_ordinary_tools_dont_mark_the_chat(chat, monkeypatch):
    stream = chat_service.create_stream("general", "q")
    _send_with_tool(chat, stream["id"], "web_search", monkeypatch)
    assert chat_service.get_stream(stream["id"]).get("pending_job") is None


def test_a_stale_marker_expires(chat, monkeypatch):
    # A crashed background process never posts; don't spin forever.
    stream = chat_service.create_stream("general", "q")
    _send_with_tool(chat, stream["id"], "think_deeply", monkeypatch)
    chat_service.get_stream(stream["id"])["pending_job"]["started"] = time.time() - 21 * 60
    assert chat_service.get_stream(stream["id"]).get("pending_job") is None
    assert all(s.get("pending_job") is None for s in chat_service.list_streams())
