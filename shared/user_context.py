"""Compiles config.yaml's optional `user:` block — facts about the user the
assistant should always know — into a section appended to the system prompt,
for voice and text chat alike.

Put it in the persona's gitignored config.local.yaml, since it's personal:

    user:
      location: Tacoma, WA
"""
from typing import Any


def build_user_prompt(user_cfg: dict[str, Any] | None) -> str:
    """Render the `user:` block, or "" when there's nothing to say."""
    location = str((user_cfg or {}).get("location") or "").strip()
    if not location:
        return ""
    return (
        f"ABOUT THE USER — they live in {location}. For anything local "
        f"(\"near me\", nearby jobs, stores, weather, opening hours), assume "
        f"{location} instead of asking, and include it in web searches."
    )
