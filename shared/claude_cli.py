"""The one place the runtime runs the `claude` CLI for a one-shot answer.

Claude work goes through the CLI so it runs on the user's Claude Code
subscription, never the billed Anthropic API. The CLI prefers an API key when
one is in its environment, so every launch here (and every other place that
starts `claude`, via claude_env) strips the key variables first.

run_claude never raises: a voice turn waiting on a tool result is better
served by a readable error string than by an exception.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass

# Variables that would make the CLI bill an API account instead of the subscription.
_API_KEY_VARS = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")


@dataclass(frozen=True)
class ClaudeResult:
    ok: bool
    text: str
    error: str


def claude_env() -> dict[str, str]:
    """A copy of this process's environment that's safe to start `claude` with."""
    return {k: v for k, v in os.environ.items() if k not in _API_KEY_VARS}


def run_claude(
    prompt: str,
    *,
    model: str | None = None,
    allowed_tools: list[str] | None = None,
    timeout: float = 120,
) -> ClaudeResult:
    if shutil.which("claude") is None:
        return ClaudeResult(ok=False, text="", error="claude CLI not found on PATH")

    argv = ["claude"]
    if model:
        argv += ["--model", model]
    # --allowedTools is variadic (commander.js) — it greedily consumes every
    # following arg as another tool name, including the prompt, unless the
    # prompt comes first.
    argv += ["-p", prompt]
    if allowed_tools:
        argv += ["--allowedTools", *allowed_tools]

    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, env=claude_env())
    except subprocess.TimeoutExpired:
        return ClaudeResult(ok=False, text="", error=f"claude CLI timed out after {timeout:g}s")

    if result.returncode != 0:
        return ClaudeResult(ok=False, text="", error=result.stderr.strip() or "unknown error")
    return ClaudeResult(ok=True, text=result.stdout.strip(), error="")
