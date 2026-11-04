"""config.yaml's `user:` block — facts about the user the assistant should
know (e.g. where they live, for "near me" questions), kept in the
machine-local config.local.yaml so they stay out of git."""

from shared.user_context import build_user_prompt


def test_no_user_block_adds_nothing():
    assert build_user_prompt(None) == ""
    assert build_user_prompt({}) == ""


def test_location_is_stated_for_near_me_questions():
    section = build_user_prompt({"location": "Tacoma, WA"})
    assert "Tacoma, WA" in section
    assert "near me" in section


def test_blank_values_are_skipped():
    assert build_user_prompt({"location": "  "}) == ""


def test_text_chat_prompt_includes_the_user_block(tmp_path):
    from app.services.chat_service import _build_system_prompt

    prompt = _build_system_prompt({"ollama": {"system_prompt": "BASE"}, "user": {"location": "Tacoma, WA"}})
    assert prompt.startswith("BASE") and "Tacoma, WA" in prompt


def test_voice_prompt_includes_the_user_block(minimal_config):
    from unittest.mock import patch

    from voice.orchestrator import Orchestrator

    with patch("voice.orchestrator.load_config", return_value={**minimal_config, "user": {"location": "Tacoma, WA"}}):
        o = Orchestrator()
    assert "Tacoma, WA" in o._ollama_cfg["system_prompt"]
