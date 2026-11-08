"""Ollama API client for local LLM inference with optional MCP tool calling."""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any, Callable, Generator

import requests

if TYPE_CHECKING:
    from integrations.client import MCPManager

_MAX_TOOL_ROUNDS = 5
# A long chat read cold (after a restart, or another chat used the cache)
# measured ~185 s on an M1 before the first token; 120 s turned it into a 500.
_CHAT_TIMEOUT_S = 360

# "Let me look that up" with no tool call: the turn ends and nothing is running,
# though it sounds like something is. Seen live with qwen3:8b.
_ANNOUNCES_ACTION = re.compile(
    r"\b(?:let me|i'll|i will|i'm going to|i am going to)\s+(?:go\s+ahead\s+and\s+)?(?:help you\s+)?"
    r"(?:look|check|search|find|pull|fetch|grab|get|set|add|open|run|create|draft|make|"
    r"put together|come up with|write|build|generate|plan|map out|work out)\b",
    re.IGNORECASE,
)
# "I'm (still) working on it… I'll share the findings once I have them" — a
# claim that work is underway, equally false when no tool was called.
_CLAIMS_PROGRESS = re.compile(
    r"\b(?:i'm|i am|i've been)\s+(?:still\s+)?working on\b"
    r"|\bonce i (?:have|get|hear)\b"
    r"|\bi'll (?:share|post|send|report)\b[^.!?]*\b(?:findings|results|answer|once|when)\b",
    re.IGNORECASE,
)
_REPEAT_NUDGE = (
    "You just said that exactly, word for word, and it didn't help the user. Give them the actual "
    "content they asked for now, or call the tool that can produce it (for plans or anything needing "
    "real work: think_deeply)."
)
_ACT_NOW_NUDGE = (
    "You said you would do that, or that you're working on it, but you didn't call a tool, "
    "so nothing is happening. If one of your tools can do it, call it now (for research, "
    "plans or anything needing real work: think_deeply). Otherwise answer directly, "
    "without claiming to be working on something."
)
# When a "working on it" claim survives the nudge, the user gets this instead.
_NOTHING_RUNNING = (
    "Sorry, I haven't actually started anything for that, and nothing is running right now. "
    "Ask me again and I'll hand it to Claude."
)
# A bare lowercase label alone on the first line ("local\n\nYou could…"): the
# model echoing an agent name from the routing section. Seen live with qwen3:8b.
_LEAKED_LABEL = re.compile(r"\A[a-z_]+\s*\n\s*\n")
_SENTENCE_END = re.compile(r'(?<=[.!?])\s+')
_MIN_CHUNK_LEN = 15


def _flush_chunk(buffer: str) -> tuple[list[str], str]:
    """Split buffer at sentence boundaries, accumulating until chunks reach _MIN_CHUNK_LEN."""
    parts = _SENTENCE_END.split(buffer)
    if len(parts) <= 1:
        return [], buffer

    chunks: list[str] = []
    acc = ""
    for part in parts[:-1]:
        acc = (acc + " " + part).strip() if acc else part.strip()
        if len(acc) >= _MIN_CHUNK_LEN:
            chunks.append(acc)
            acc = ""

    remainder = (acc + " " + parts[-1]).strip() if acc else parts[-1]
    return chunks, remainder


def generate_response_streaming(
    prompt: str,
    *,
    base_url: str = "http://localhost:11434",
    model: str = "llama3.2",
    system_prompt: str = "You are a concise voice assistant. Keep responses brief.",
    temperature: float = 0.7,
    max_tokens: int = 150,
    history: list[dict[str, Any]] | None = None,
    keep_alive: str | int | None = None,
) -> Generator[str, None, None]:
    """Stream LLM response, yielding complete sentence chunks as tokens arrive.

    Chunks are buffered until a sentence boundary is reached so TTS starts
    on the first complete sentence rather than waiting for the full response.
    Does not support tool calls — use generate_response() when MCP tools are needed.
    """
    url = f"{base_url.rstrip('/')}/api/chat"

    messages: list[dict[str, Any]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": prompt})

    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": True,
        "think": False,  # suppress hybrid-thinking models' <think> pass; ignored by models without one
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        },
    }
    if keep_alive is not None:
        payload["keep_alive"] = keep_alive

    buffer = ""
    with requests.post(url, json=payload, stream=True, timeout=120) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            token = data.get("message", {}).get("content", "")
            if token:
                buffer += token
                chunks, buffer = _flush_chunk(buffer)
                yield from chunks
            if data.get("done"):
                break

    remainder = buffer.strip()
    if remainder:
        yield remainder


def generate_response(
    prompt: str,
    *,
    base_url: str = "http://localhost:11434",
    model: str = "llama3.2",
    system_prompt: str = "You are a concise voice assistant. Keep responses brief.",
    temperature: float = 0.7,
    max_tokens: int = 150,
    tools: list[dict[str, Any]] | None = None,
    mcp: MCPManager | None = None,
    history: list[dict[str, Any]] | None = None,
    keep_alive: str | int | None = None,
    session_context: dict[str, Any] | None = None,
    on_tool: Callable[[str], None] | None = None,
) -> str:
    """Send prompt to Ollama and return generated text.

    When *tools* and *mcp* are provided the model may make tool calls;
    results are fed back automatically until the model emits a final
    text response (up to ``_MAX_TOOL_ROUNDS`` iterations).

    *history* is a list of prior ``{"role": ..., "content": ...}`` messages
    from the current session, prepended before the current user turn.

    *session_context* is passed through opaquely to ``mcp.call_tool`` for
    every tool call this turn makes — see MCPManager.call_tool for what it
    does with it.
    """
    url = f"{base_url.rstrip('/')}/api/chat"

    messages: list[dict[str, Any]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": prompt})

    called_a_tool = False
    nudged = False
    last_reply = next((m.get("content", "").strip() for m in reversed(history or []) if m.get("role") == "assistant"), "")
    for _ in range(_MAX_TOOL_ROUNDS):
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "think": False,  # suppress hybrid-thinking models' <think> pass; ignored by models without one
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if tools:
            payload["tools"] = tools
        if keep_alive is not None:
            payload["keep_alive"] = keep_alive

        # 120s, not 60 — a round after a terminal-routed tool call
        # (open_claude_code/ask_claude_code/open_terminal) can be feeding
        # back a large captured-output message, and a cold model load adds
        # its own real delay on top of that.
        resp = requests.post(url, json=payload, timeout=_CHAT_TIMEOUT_S)
        resp.raise_for_status()
        msg = resp.json().get("message", {})

        if not msg.get("tool_calls") and not (msg.get("content") or "").strip():
            # Neither text nor a tool call: qwen3 with thinking off sometimes
            # emits a tool call Ollama can't parse, and Ollama drops it. Letting
            # it think for this one round recovers a real answer (slower, but
            # only on these rare rounds).
            print("[llm] Empty reply — retrying this round with thinking allowed.", flush=True)
            retry = {k: v for k, v in payload.items() if k != "think"}
            resp = requests.post(url, json=retry, timeout=_CHAT_TIMEOUT_S)
            resp.raise_for_status()
            msg = resp.json().get("message", {})

        tool_calls = msg.get("tool_calls")
        if not tool_calls or not mcp:
            content = _LEAKED_LABEL.sub("", (msg.get("content") or "").strip())
            repeated = bool(content) and content == last_reply
            if not nudged and not called_a_tool and (repeated or (tools and mcp and (_ANNOUNCES_ACTION.search(content) or _CLAIMS_PROGRESS.search(content)))):
                nudged = True
                print("[llm] Reply repeated itself or promised without acting — nudging once.", flush=True)
                messages.append(msg)
                messages.append({"role": "system", "content": _REPEAT_NUDGE if repeated else _ACT_NOW_NUDGE})
                continue
            if nudged and not called_a_tool and tools and mcp and _CLAIMS_PROGRESS.search(content):
                print("[llm] Still claiming to be working after the nudge — telling the user the truth.", flush=True)
                return _NOTHING_RUNNING
            return content

        called_a_tool = True
        messages.append(msg)
        for tc in tool_calls:
            func = tc.get("function", {})
            name = func.get("name", "")
            args = func.get("arguments", {})
            print(f"[mcp] Calling tool '{name}'...", flush=True)
            if on_tool:
                on_tool(name)  # e.g. so the chat UI can say "searching the web…"
            # call_tool_with_follow_ups also runs any tools config.yaml's
            # mcp.servers[].follow_up declares for *name* (e.g. an error
            # check right after a script edit) — deterministically, rather
            # than trusting this round's model to remember to ask for it
            # itself. Each extra result becomes its own tool message, same
            # as if the model had called it directly.
            for called_name, result in mcp.call_tool_with_follow_ups(name, args, session_context):
                if called_name != name:
                    print(f"[mcp] Follow-up: calling tool '{called_name}'...", flush=True)
                messages.append({"role": "tool", "content": str(result)})

    return msg.get("content", "").strip()
