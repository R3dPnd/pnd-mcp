"""Plumbing for think_deeply: typed chat passes its stream id to tools, and
/announce can post into a specific stream."""

from fastapi.testclient import TestClient

from app.main import app
from app.services import chat_service
from tests.app.test_announce import chat  # noqa: F401  (fixture)


def test_send_message_passes_the_stream_id_to_tools(chat, monkeypatch):
    seen = {}
    monkeypatch.setattr(chat_service, "get_shared_manager", lambda: type("M", (), {"tools": []})())
    monkeypatch.setattr(chat_service, "generate_response",
                        lambda text, **kw: seen.update(kw.get("session_context") or {}) or "ok")
    stream = chat_service.create_stream("general", "plans")
    chat_service.send_message(stream["id"], "plan my degree")
    assert seen == {"focus_area": "general", "stream_id": stream["id"]}


def test_announce_into_a_specific_stream(chat):
    stream = chat_service.create_stream("general", "Degree plan")
    body = TestClient(app).post("/api/v1/announce", json={
        "text": "Claude's plan is ready.", "stream_id": stream["id"], "chat_text": "## Year 1 …"}).json()
    assert body["stream_id"] == stream["id"]
    assert chat_service.get_stream(stream["id"])["messages"][-1]["content"] == "## Year 1 …"


def test_announce_into_a_missing_stream_falls_back_to_a_named_one(chat):
    body = TestClient(app).post("/api/v1/announce", json={
        "text": "Done.", "stream_id": "gone", "chat_title": "Claude answers", "chat_text": "answer"}).json()
    assert chat_service.get_stream(body["stream_id"])["title"] == "Claude answers"
