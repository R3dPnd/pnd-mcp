#!/usr/bin/env python3
"""MCP server for general Claude reasoning and web research.

Split out of claude_code_server so a persona that isn't a coding partner can
have research and reasoning without the project/Claude Code session tools.
claude_code_server still exposes these two tool names by delegating here, so
existing configs that route to them on the `projects` server keep working.

Everything runs through the `claude` CLI on the user's subscription (see
shared/claude_cli.py) — never the billed Anthropic API.

Exposed tools:
  ask_claude  — route a query to Claude for deep reasoning/analysis
  web_search  — current/up-to-date info via Claude's built-in web search
"""

import subprocess
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from shared.claude_cli import run_claude

mcp = FastMCP("claude")


@mcp.tool()
def ask_claude(question: str, context: str = "", depth: str = "deep") -> str:
    """Route a question to Claude for deep reasoning or analysis.

    Use this when the query needs broad knowledge, nuanced reasoning, detailed
    explanation, or creative thinking beyond what the local model handles well.
    Runs through the `claude` CLI (your existing Claude Code subscription) —
    not the billed Anthropic API. Returns a spoken-friendly response (no
    markdown, 1-3 sentences).

    Args:
        question: The question or task for Claude.
        context: Optional extra context to help Claude give a better answer.
        depth: "fast" for a quick/cheap answer (haiku), "deep" (default) for
            the CLI's normal model — better for hard reasoning or analysis.
    """
    prompt = f"{context.strip()}\n\n{question.strip()}" if context.strip() else question.strip()

    # Append TTS formatting instruction so the response is speakable
    full_prompt = (
        f"{prompt}\n\n"
        "Answer in 1-3 concise spoken sentences. "
        "No markdown, bullet points, or formatting — your response will be read aloud."
    )

    result = run_claude(full_prompt, model="haiku" if depth == "fast" else None, timeout=60)
    if not result.ok:
        return f"Claude returned an error: {result.error}"
    return result.text or "Claude returned an empty response."


@mcp.tool()
def web_search(query: str) -> str:
    """Search the web for current information — news, prices, recent
    releases, anything that might be after the local model's knowledge
    cutoff. Runs through the `claude` CLI's built-in web search (your
    existing subscription), not a separate billed API.

    Args:
        query: What to search for / the question to answer using the web.
    """
    prompt = (
        f"Search the web for: {query.strip()}\n\n"
        "Answer in 1-3 concise spoken sentences based on what you find. "
        "No markdown, bullet points, or formatting — your response may be read aloud."
    )

    result = run_claude(prompt, allowed_tools=["WebSearch"], timeout=120)
    if not result.ok:
        if "timed out" in result.error:
            return "Web search timed out."
        return f"Web search error: {result.error}"
    return result.text or "No answer found."


_RUNTIME_DIR = Path(__file__).resolve().parents[2]


@mcp.tool()
def think_deeply(question: str, stream_id: str = "") -> str:
    """Hand a request that needs real work to Claude in the background — a plan,
    a schedule, a comparison, a multi-step or researched answer, or whenever
    the user says "ask Claude" / "think harder". Returns at once; the full
    answer is posted into this chat and announced when it's ready.

    Args:
        question: What to work out, in full (include the details the user gave).
        stream_id: Filled in automatically — leave empty.
    """
    subprocess.Popen(
        [sys.executable, "-m", "integrations.deep_think", "--stream-id", stream_id, "--question", question],
        cwd=str(_RUNTIME_DIR), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return "On it — I've asked Claude to work that out. I'll post the answer here and tell you when it's ready."


if __name__ == "__main__":
    mcp.run()
