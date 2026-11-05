"""Prompts for the two Claude calls a hunt makes — screening JSearch postings
against the user's criteria and resume, and finding async gig work JSearch
doesn't index — and tolerant parsing of their JSON answers."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

_DESCRIPTION_CHARS = 1500
_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


@dataclass(frozen=True)
class Screen:
    keep: bool
    score: int
    fit: str
    suggestion: str


def _criteria_block(criteria: dict[str, Any], location: str) -> str:
    return (
        f"- Lives in {location}.\n"
        f"- Schedule: {criteria.get('schedule', '')}\n"
        f"- Pay floor: ${criteria.get('pay_floor_hourly', 25)}/hour (or the per-task equivalent).\n"
        f"- Kinds of work wanted: {', '.join(criteria.get('kinds') or [])}\n"
        f"- Automatic no: {', '.join(criteria.get('exclude') or [])}\n"
    )


def _json_array(text: str) -> list[Any]:
    fenced = _FENCE.search(text)
    body = fenced.group(1) if fenced else text
    start, end = body.find("["), body.rfind("]")
    if start == -1 or end < start:
        raise ValueError("no JSON array in reply")
    data = json.loads(body[start:end + 1])
    if not isinstance(data, list):
        raise ValueError("reply is not a JSON array")
    return data


def screen_prompt(candidates: list[dict], resume: str, criteria: dict[str, Any], location: str) -> str:
    postings = [
        {**{k: c.get(k) for k in ("key", "title", "org", "pay", "location", "remote")},
         "description": (c.get("description") or "")[:_DESCRIPTION_CHARS]}
        for c in candidates
    ]
    return (
        "You are screening job postings for one person. Judge each posting against their resume and "
        "their constraints below. Use only what the resume and the posting say — never invent facts "
        "about the person.\n\n"
        f"THEIR CONSTRAINTS:\n{_criteria_block(criteria, location)}\n"
        f"THEIR RESUME:\n{resume}\n\n"
        f"POSTINGS (JSON):\n{json.dumps(postings, indent=1)}\n\n"
        "Reply with ONLY a JSON array, one object per posting:\n"
        '[{"key": "<the posting key>", "keep": true|false, "score": 0-100, '
        '"fit": "<one sentence tying this posting to their resume AND their schedule>", '
        '"suggestion": "<one sentence: what to emphasize when applying, or a caveat>"}]\n'
        "keep=false for anything that breaks a constraint (fixed Mon-Thu daytime hours, on-call, "
        "in-office Mon-Thu, full-time, stated pay under the floor)."
    )


def parse_screen(text: str) -> dict[str, Screen]:
    screens = {}
    for item in _json_array(text):
        if not isinstance(item, dict) or not item.get("key"):
            continue
        try:
            screens[item["key"]] = Screen(keep=bool(item.get("keep")), score=int(item.get("score", 0)),
                                          fit=str(item.get("fit", "")), suggestion=str(item.get("suggestion", "")))
        except (TypeError, ValueError):
            continue
    return screens


def gig_prompt(criteria: dict[str, Any], location: str, resume_summary: str, known_urls: list[str]) -> str:
    known = "\n".join(known_urls) or "(none)"
    return (
        "Search the web for CURRENTLY OPEN async gig work for a software engineer: AI code "
        "evaluation and training platforms, paid code review, coding bounties, and short freelance "
        "development work that can be done in short bursts.\n\n"
        f"THEIR CONSTRAINTS:\n{_criteria_block(criteria, location)}\n"
        f"ABOUT THEM: {resume_summary}\n\n"
        f"Skip anything at these URLs (already reported):\n{known}\n\n"
        "Only include opportunities you found on a real page in this search, with that page's URL. "
        "Reply with ONLY a JSON array (empty if nothing fits):\n"
        '[{"title": "...", "org": "...", "url": "https://...", "pay": "<as stated, or empty>", "kind": "gig"}]'
    )


def parse_gigs(text: str) -> list[dict]:
    """Gig leads with a real http(s) URL; [] when the reply has no JSON
    (gig results are a bonus — their absence mustn't sink the hunt)."""
    try:
        items = _json_array(text)
    except (ValueError, json.JSONDecodeError):
        return []
    return [
        {**i, "kind": "gig"} for i in items
        if isinstance(i, dict) and str(i.get("url", "")).startswith(("http://", "https://"))
    ]
