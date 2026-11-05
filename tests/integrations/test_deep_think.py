"""integrations.deep_think — Claude works on a question in the background and
the answer is posted back into the chat it came from."""

import pytest

from integrations import deep_think
from shared.claude_cli import ClaudeResult

HISTORY = [
    {"role": "user", "content": "Help me plan my UW Tacoma MS CSS graduation, one course per semester."},
    {"role": "assistant", "content": "I'll help you create a sample graduation plan…"},
]


def test_prompt_carries_the_conversation_question_and_who_the_user_is():
    prompt = deep_think.build_prompt("show me the plan", HISTORY, location="Tacoma, WA")
    assert "UW Tacoma MS CSS" in prompt and "show me the plan" in prompt and "Tacoma, WA" in prompt
    assert "web" in prompt.lower()  # it may research (program pages)


def test_run_posts_the_answer_into_the_same_stream(monkeypatch):
    calls, posted = [], []
    claude = lambda prompt, allowed_tools=None, timeout=0: calls.append((allowed_tools, timeout)) or \
        ClaudeResult(ok=True, text="## Fall 2026\nTCSS 598 (part 2)…", error="")
    post = lambda body: posted.append(body) or True
    deep_think.run("show me the plan", stream_id="s1", history=HISTORY, location="Tacoma, WA", claude=claude, post=post)
    ((tools, timeout),) = calls
    assert "WebSearch" in tools and timeout >= 600
    ((body,),) = [(b,) for b in posted]
    assert body["stream_id"] == "s1" and body["chat_text"].startswith("## Fall 2026")
    assert "ready" in body["text"].lower() and "http" not in body["text"]


def test_run_reports_a_failure_in_the_chat(monkeypatch):
    posted = []
    deep_think.run("q", stream_id="s1", history=[], location="", post=lambda b: posted.append(b) or True,
                   claude=lambda *a, **k: ClaudeResult(ok=False, text="", error="claude CLI not found on PATH"))
    assert "couldn't" in posted[0]["text"].lower() and "claude CLI not found" in posted[0]["chat_text"]


def test_history_for_reads_the_stream(tmp_path, monkeypatch):
    import json
    (tmp_path / "work_streams.json").write_text(json.dumps([{"id": "s1", "messages": HISTORY}]))
    assert deep_think.history_for("s1", tmp_path) == HISTORY
    assert deep_think.history_for("nope", tmp_path) == []
