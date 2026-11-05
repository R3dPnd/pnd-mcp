"""think_deeply: Claude works on a question in the background — a plan, a
comparison, anything that needs more than the local model's quick reply —
and the answer is posted back into the chat it was asked from, with a short
spoken "it's ready". Started detached by claude_server.think_deeply, so the
chat turn returns at once (the user chose quick replies over waiting)."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from shared.claude_cli import ClaudeResult

TIMEOUT = 900
FALLBACK_TITLE = "Claude answers"


def history_for(stream_id: str, base: Path) -> list[dict[str, Any]]:
    """The conversation so far in that chat stream (from work_streams.json)."""
    path = base / "work_streams.json"
    if not path.is_file():
        return []
    stream = next((s for s in json.loads(path.read_text() or "[]") if s.get("id") == stream_id), None)
    return [{"role": m["role"], "content": m["content"]} for m in (stream or {}).get("messages", [])]


def build_prompt(question: str, history: list[dict[str, Any]], location: str = "") -> str:
    convo = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in history[-20:]) or "(none)"
    about = f"The user lives in {location}. " if location else ""
    return (
        "You're helping Akane, a personal voice assistant, with a request her quick local model "
        "couldn't handle. Do the actual work and give the full answer — don't promise, don't ask "
        "the user to look things up themselves. Research on the web when facts matter (official "
        "program pages, requirements, current details) and say where key facts came from. "
        f"{about}Format for reading in a chat: short headings and lists are fine.\n\n"
        f"CONVERSATION SO FAR:\n{convo}\n\nREQUEST:\n{question}"
    )


def run(question: str, *, stream_id: str, history: list[dict[str, Any]], location: str,
        claude: Callable[..., ClaudeResult], post: Callable[[dict], bool]) -> None:
    result = claude(build_prompt(question, history, location), allowed_tools=["WebSearch", "WebFetch"],
                    timeout=TIMEOUT)
    if result.ok and result.text.strip():
        body = {"text": "Claude's answer is ready — it's in the chat.", "chat_text": result.text.strip()}
    else:
        body = {"text": "Sorry — Claude couldn't finish that one. The details are in the chat.",
                "chat_text": f"Claude couldn't finish this: {result.error or 'empty answer'}"}
    post({**body, "stream_id": stream_id, "chat_title": FALLBACK_TITLE})
