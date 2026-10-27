"""claude_server holds the general (non-coding) Claude tools so a persona can
have research/reasoning without the project/coding tools. claude_code_server
still exposes the same two tool names (Dann's config routes to them there) by
delegating, so its behavior must match claude_server's exactly."""

import pytest

from integrations.servers import claude_code_server, claude_server
from shared.claude_cli import ClaudeResult


@pytest.fixture()
def fake_claude(monkeypatch):
    calls = []
    state = {"result": ClaudeResult(ok=True, text="answer", error="")}

    def _run(prompt, **kwargs):
        calls.append({"prompt": prompt, **kwargs})
        return state["result"]

    monkeypatch.setattr(claude_server, "run_claude", _run)
    return calls, state


def test_ask_claude_fast_uses_haiku_and_60s(fake_claude):
    calls, _ = fake_claude
    assert claude_server.ask_claude("q", depth="fast") == "answer"
    assert calls[0]["model"] == "haiku" and calls[0]["timeout"] == 60
    assert "1-3 concise spoken sentences" in calls[0]["prompt"]


def test_ask_claude_deep_uses_default_model(fake_claude):
    calls, _ = fake_claude
    claude_server.ask_claude("q", context="ctx")
    assert calls[0].get("model") is None
    assert calls[0]["prompt"].startswith("ctx\n\nq")


def test_ask_claude_error_message(fake_claude):
    _, state = fake_claude
    state["result"] = ClaudeResult(ok=False, text="", error="bad")
    assert claude_server.ask_claude("q") == "Claude returned an error: bad"


def test_web_search_allows_websearch_with_120s(fake_claude):
    calls, _ = fake_claude
    assert claude_server.web_search("x") == "answer"
    assert calls[0]["allowed_tools"] == ["WebSearch"] and calls[0]["timeout"] == 120


def test_web_search_error_message(fake_claude):
    _, state = fake_claude
    state["result"] = ClaudeResult(ok=False, text="", error="bad")
    assert claude_server.web_search("x") == "Web search error: bad"


def test_web_search_timeout_message(fake_claude):
    _, state = fake_claude
    state["result"] = ClaudeResult(ok=False, text="", error="claude CLI timed out after 120s")
    assert claude_server.web_search("x") == "Web search timed out."


def test_claude_code_server_delegates(fake_claude):
    assert claude_code_server.ask_claude("q") == claude_server.ask_claude("q")
    assert claude_code_server.web_search("x") == claude_server.web_search("x")
