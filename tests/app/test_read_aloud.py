"""POST /api/v1/voice/speak and /voice/speak/stop — the chat's speaker button
asking the persona to read one of its messages aloud."""

from fastapi.testclient import TestClient

import app.main
from app.main import app as api
from voice.event_bus import bus


class FakeOrchestrator:
    _running = True

    def __init__(self):
        self.stopped = False

    def stop_speaking(self):
        self.stopped = True


def test_speak_queues_the_text(monkeypatch):
    monkeypatch.setattr(app.main, "orchestrator", FakeOrchestrator())
    events = []
    listener = lambda t, p: events.append((t, p))
    bus.subscribe(listener)
    try:
        r = TestClient(api).post("/api/v1/voice/speak", json={"text": "Here's the plan."})
    finally:
        bus.unsubscribe(listener)
    assert r.status_code == 200
    assert ("speak", {"text": "Here's the plan."}) in events


def test_stop_stops_reading(monkeypatch):
    orch = FakeOrchestrator()
    monkeypatch.setattr(app.main, "orchestrator", orch)
    assert TestClient(api).post("/api/v1/voice/speak/stop").status_code == 200
    assert orch.stopped


def test_without_a_voice_pipeline_it_says_so(monkeypatch):
    monkeypatch.setattr(app.main, "orchestrator", None)
    assert TestClient(api).post("/api/v1/voice/speak", json={"text": "hi"}).status_code == 503


def test_empty_text_is_rejected(monkeypatch):
    monkeypatch.setattr(app.main, "orchestrator", FakeOrchestrator())
    assert TestClient(api).post("/api/v1/voice/speak", json={"text": "  "}).status_code == 400
