"""The health endpoint names the persona's API, not the original Dann one."""

from fastapi.testclient import TestClient

from app.main import app
from shared.persona import get_persona


def test_health_names_the_persona(tmp_path, monkeypatch):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("persona:\n  name: Akane\n")
    monkeypatch.setenv("PND_CONFIG_PATH", str(cfg))
    get_persona.cache_clear()
    try:
        body = TestClient(app).get("/api/v1/health").json()
    finally:
        get_persona.cache_clear()
    assert body["service"] == "Akane API"
