"""shared/claude_cli.py is the one place the runtime shells out to `claude`
for a one-shot answer. Its job is to keep Claude usage on the user's
subscription: never hand the CLI an API key, and never raise into a voice
turn — a missing binary or a timeout becomes a readable error."""

import subprocess
from types import SimpleNamespace

import pytest

from shared import claude_cli
from shared.claude_cli import ClaudeResult, claude_env, run_claude


@pytest.fixture()
def fake_run(monkeypatch):
    calls = {}

    def _run(argv, **kwargs):
        calls["argv"] = argv
        calls["env"] = kwargs.get("env")
        calls["timeout"] = kwargs.get("timeout")
        return SimpleNamespace(returncode=calls.get("returncode", 0), stdout=" hi \n", stderr="boom")

    monkeypatch.setattr(claude_cli.shutil, "which", lambda _: "/usr/local/bin/claude")
    monkeypatch.setattr(claude_cli.subprocess, "run", _run)
    return calls


def test_claude_env_strips_api_keys(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-x")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "t")
    env = claude_env()
    assert "ANTHROPIC_API_KEY" not in env
    assert "ANTHROPIC_AUTH_TOKEN" not in env
    assert "PATH" in env


def test_run_claude_puts_prompt_before_allowed_tools_and_uses_clean_env(fake_run, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-x")
    result = run_claude("q", model="haiku", allowed_tools=["WebSearch"], timeout=30)
    assert fake_run["argv"] == ["claude", "--model", "haiku", "-p", "q", "--allowedTools", "WebSearch"]
    assert "ANTHROPIC_API_KEY" not in fake_run["env"]
    assert fake_run["timeout"] == 30
    assert result == ClaudeResult(ok=True, text="hi", error="")


def test_run_claude_nonzero_exit_returns_stderr(fake_run):
    fake_run["returncode"] = 1
    r = run_claude("q")
    assert not r.ok and r.error == "boom"


def test_run_claude_missing_binary_returns_error(monkeypatch):
    monkeypatch.setattr(claude_cli.shutil, "which", lambda _: None)
    r = run_claude("q")
    assert not r.ok and "claude CLI not found" in r.error


def test_run_claude_timeout_returns_error(monkeypatch):
    monkeypatch.setattr(claude_cli.shutil, "which", lambda _: "/usr/local/bin/claude")

    def _timeout(argv, **kwargs):
        raise subprocess.TimeoutExpired(argv, kwargs["timeout"])

    monkeypatch.setattr(claude_cli.subprocess, "run", _timeout)
    r = run_claude("q", timeout=5)
    assert not r.ok and "timed out" in r.error
