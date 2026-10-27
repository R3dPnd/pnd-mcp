"""The prompt builder must only ever use the `claude` CLI — never fall back to
the billed anthropic SDK, even when ANTHROPIC_API_KEY is set."""

from fastapi.testclient import TestClient

from app.api.v1.endpoints import prompt_builder
from app.main import app


def test_no_sdk_fallback_when_cli_missing(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-x")
    monkeypatch.setattr("shared.claude_cli.shutil.which", lambda _: None)
    assert not hasattr(prompt_builder, "_call_via_sdk")
    r = TestClient(app).post("/api/v1/prompt-builder", json={"thoughts": "hello"})
    assert r.status_code == 503
    assert "claude CLI not found" in r.json()["detail"]
