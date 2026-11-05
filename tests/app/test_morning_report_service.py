"""app.services.morning_report_service — when the morning report is delivered."""

import threading

import pytest

from app.services import morning_report_service as svc
from voice.event_bus import bus


@pytest.fixture()
def recorder(monkeypatch, tmp_data_dir):
    said, posted = [], []
    monkeypatch.setattr(svc, "due", lambda data_dir, today, now: svc.Delivery(spoken=["Morning."], chat=["## 1."]))
    monkeypatch.setattr(svc.chat_service, "post_assistant_message", lambda title, text: posted.append((title, text)) or "s1")
    listener = lambda t, p: said.append(p["text"]) if t == "announce" else None
    bus.subscribe(listener)
    yield said, posted
    bus.unsubscribe(listener)
    svc.uninstall()


def test_ready_event_triggers_one_delivery(recorder, monkeypatch):
    said, posted = recorder
    svc.install(voice_pipeline=True)
    bus.emit("state.changed", {"running": True})
    assert said == ["Morning."] and posted == [("Morning report", "## 1.")]


def test_no_delivery_without_a_trigger(recorder):
    said, posted = recorder
    svc.install(voice_pipeline=True)
    bus.emit("state.changed", {"running": False})
    bus.emit("turn.llm", {})
    assert said == [] and posted == []


@pytest.mark.parametrize("event", ["session.start", "chat.turn"])
def test_first_interaction_triggers_delivery(recorder, event):
    said, _ = recorder
    svc.install(voice_pipeline=True)
    bus.emit(event, {})
    assert said == ["Morning."]


def test_silent_mode_delivers_at_startup_to_chat(recorder):
    said, posted = recorder
    svc.install(voice_pipeline=False)
    assert posted == [("Morning report", "## 1.")]


def test_concurrent_triggers_deliver_once(recorder, monkeypatch):
    said, posted = recorder
    calls = {"n": 0}

    def once(data_dir, today, now):
        calls["n"] += 1
        return svc.Delivery(spoken=["Morning."], chat=[]) if calls["n"] == 1 else svc.Delivery(spoken=[], chat=[])

    monkeypatch.setattr(svc, "due", once)
    svc.install(voice_pipeline=True)
    threads = [threading.Thread(target=bus.emit, args=("chat.turn", {})) for _ in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert said == ["Morning."]


def test_api_startup_installs_delivery_in_silent_mode(tmp_data_dir, tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import app

    cfg = tmp_path / "config.yaml"
    cfg.write_text("ollama: {}\n")
    monkeypatch.setenv("PND_CONFIG_PATH", str(cfg))
    monkeypatch.setenv("NO_VOICE", "1")
    seen = []
    monkeypatch.setattr(svc, "install", lambda voice_pipeline: seen.append(voice_pipeline))
    with TestClient(app):
        pass
    assert seen == [False]
