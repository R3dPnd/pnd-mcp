"""POST /api/v1/announce and chat_service.post_assistant_message — how
background work (the job hunt, the morning report) tells the user something."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import chat_service
from voice.event_bus import bus


@pytest.fixture()
def chat(tmp_data_dir, tmp_path, monkeypatch):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("focus_areas:\n  - {name: off, description: d, enabled: false}\n"
                   "  - {name: general, description: d}\n  - {name: other, description: d}\n")
    monkeypatch.setenv("PND_CONFIG_PATH", str(cfg))
    monkeypatch.setattr(chat_service, "_streams", {})
    monkeypatch.setattr(chat_service, "_loaded", False)
    return chat_service


def test_post_assistant_message_reuses_the_stream(chat):
    first = chat.post_assistant_message("Morning report", "one")
    second = chat.post_assistant_message("Morning report", "two")
    assert first == second
    stream = chat.get_stream(first)
    assert [(m["role"], m["content"]) for m in stream["messages"]] == [("assistant", "one"), ("assistant", "two")]


def test_post_assistant_message_creates_under_first_focus_area(chat):
    stream = chat.get_stream(chat.post_assistant_message("Morning report", "hi"))
    assert stream["focus_area"] == "general" and stream["title"] == "Morning report"


def test_announce_endpoint_emits_and_posts(chat):
    events = []
    listener = lambda t, p: events.append((t, p))
    bus.subscribe(listener)
    try:
        body = TestClient(app).post("/api/v1/announce",
                                    json={"text": "Your hunt is done.", "chat_title": "Morning report"}).json()
    finally:
        bus.unsubscribe(listener)
    assert ("announce", {"text": "Your hunt is done."}) in events
    assert body["ok"] is True
    assert chat.get_stream(body["stream_id"])["messages"][-1]["content"] == "Your hunt is done."


def test_announce_without_chat_title_only_speaks(chat):
    body = TestClient(app).post("/api/v1/announce", json={"text": "Hi."}).json()
    assert body == {"ok": True, "stream_id": None}


def test_announce_endpoint_rejects_blank_text(chat):
    assert TestClient(app).post("/api/v1/announce", json={"text": "  "}).status_code == 400


def test_announce_can_post_different_text_to_the_chat(chat):
    body = TestClient(app).post("/api/v1/announce", json={
        "text": "Your job hunt is done. 2 new leads.", "chat_title": "Morning report", "chat_text": "## 9. X — Y"}).json()
    assert chat.get_stream(body["stream_id"])["messages"][-1]["content"] == "## 9. X — Y"


def test_posting_tells_the_dashboard_to_refresh(chat):
    # The chat panel only fetched on mount/selection, so a posted report never
    # appeared until a reload (review I-2).
    events = []
    listener = lambda t, p: events.append((t, p))
    bus.subscribe(listener)
    try:
        stream_id = chat.post_assistant_message("Morning report", "hi")
    finally:
        bus.unsubscribe(listener)
    assert ("chat.posted", {"stream_id": stream_id}) in events
