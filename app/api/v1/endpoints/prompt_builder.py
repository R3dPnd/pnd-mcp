"""POST /api/v1/prompt-builder — consolidate thoughts/goals/notes via Claude.

Uses the locally-authenticated `claude` CLI (Claude Code) via
shared/claude_cli.py, so it runs on the user's subscription. There is
deliberately no fallback to the billed anthropic SDK.
"""

import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from shared.claude_cli import run_claude

router = APIRouter()


class CustomSection(BaseModel):
    title: str = "Section"
    content: str = ""


class PromptBuilderRequest(BaseModel):
    thoughts: str = ""
    goals: str = ""
    notes: str = ""
    custom_sections: list[CustomSection] = []


class PromptBuilderResponse(BaseModel):
    recommended_model: str
    prompt: str
    reasoning: str


_META_PROMPT = """\
You are a prompt engineering expert. A user has provided raw thoughts, goals, and notes. Your task is to:

1. Recommend the best Claude model for this task from the list below
2. Craft a clear, effective, ready-to-use prompt that consolidates their inputs

Available models:
- claude-opus-4-6: Best for complex reasoning, deep analysis, research, nuanced multi-step tasks
- claude-sonnet-4-6: Best for balanced tasks — smart, fast, coding, writing, general use
- claude-haiku-4-5-20251001: Best for quick, simple tasks — classification, extraction, short answers

User's raw input:
{consolidated}

Respond with ONLY valid JSON in this exact format, no markdown fences:
{{
  "recommended_model": "<model_id>",
  "reasoning": "<1-2 sentences explaining why this model fits the task>",
  "prompt": "<the crafted, optimized, ready-to-use prompt>"
}}"""


def _parse_response(text: str) -> dict:
    """Strip optional markdown fences and parse JSON."""
    if text.startswith("```"):
        parts = text.split("```")
        for part in parts:
            stripped = part.strip()
            if stripped.startswith("json"):
                stripped = stripped[4:].strip()
            if stripped.startswith("{"):
                text = stripped
                break
    return json.loads(text)


@router.post("", response_model=PromptBuilderResponse, summary="Build optimised prompt from consolidated thoughts")
async def build_prompt(req: PromptBuilderRequest) -> PromptBuilderResponse:
    sections: list[str] = []
    if req.thoughts.strip():
        sections.append(f"## Thoughts\n{req.thoughts.strip()}")
    if req.goals.strip():
        sections.append(f"## Goals\n{req.goals.strip()}")
    if req.notes.strip():
        sections.append(f"## Notes\n{req.notes.strip()}")
    for sec in req.custom_sections:
        if sec.content.strip():
            sections.append(f"## {sec.title}\n{sec.content.strip()}")

    if not sections:
        raise HTTPException(status_code=422, detail="At least one non-empty section is required.")

    consolidated = "\n\n".join(sections)
    prompt = _META_PROMPT.format(consolidated=consolidated)

    result = run_claude(prompt, timeout=120)
    if not result.ok:
        raise HTTPException(
            status_code=503,
            detail=f"Claude CLI unavailable: {result.error}. Ensure `claude` (Claude Code) is on PATH and signed in.",
        )
    text = result.text

    try:
        data = _parse_response(text)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to parse Claude response as JSON: {exc}\n\nRaw: {text[:500]}",
        )

    return PromptBuilderResponse(
        recommended_model=data.get("recommended_model", "claude-sonnet-4-6"),
        prompt=data.get("prompt", ""),
        reasoning=data.get("reasoning", ""),
    )
