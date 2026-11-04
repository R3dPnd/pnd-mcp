"""GET /api/v1/persona — what the dashboard shows as the assistant's name and
wake phrase. Defaults must match the pre-persona hardcoded Dann values."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from shared.persona import get_persona


@pytest.fixture()
def client_with_config(tmp_path, monkeypatch):
    def _make(text: str) -> TestClient:
        cfg = tmp_path / "config.yaml"
        cfg.write_text(text)
        monkeypatch.setenv("PND_CONFIG_PATH", str(cfg))
        get_persona.cache_clear()
        return TestClient(app)

    yield _make
    get_persona.cache_clear()


def test_persona_endpoint_defaults(client_with_config):
    client = client_with_config("ollama: {}\n")
    assert client.get("/api/v1/persona").json() == {"name": "Dann", "wake_phrase": "ok Dann", "theme": ""}


def test_persona_endpoint_reads_config(client_with_config):
    client = client_with_config("persona:\n  name: Akane\n  wake_phrase: ok Akane\n")
    assert client.get("/api/v1/persona").json() == {"name": "Akane", "wake_phrase": "ok Akane", "theme": ""}


def test_persona_endpoint_reports_the_ui_theme(client_with_config):
    client = client_with_config("persona:\n  name: Akane\n  theme: rose\n")
    assert client.get("/api/v1/persona").json()["theme"] == "rose"
