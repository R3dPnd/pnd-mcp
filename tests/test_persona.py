"""Unit tests for shared/persona.py — the persona block's defaults must match
the pre-extraction hardcoded Dann values exactly, so a persona repo without a
`persona:` block (dann-of-thursday) behaves as it always has."""

from pathlib import Path

from shared.persona import data_dir, get_persona, persona_from_config


def test_defaults_match_dann_when_no_persona_block():
    p = persona_from_config({})
    assert (p.name, p.wake_phrase, p.api_port, p.ui_port) == ("Dann", "ok Dann", 8000, 3000)
    assert p.data_dir == Path.home() / ".dann"


def test_none_config_gives_defaults():
    assert persona_from_config(None).name == "Dann"


def test_persona_block_overrides_and_expands_tilde():
    p = persona_from_config({"persona": {
        "name": "Akane", "wake_phrase": "ok Akane", "data_dir": "~/.akane", "api_port": 8100,
    }})
    assert p.name == "Akane" and p.api_port == 8100 and p.ui_port == 3000
    assert p.data_dir == Path.home() / ".akane"


def test_data_dir_prefers_env_and_creates_it(tmp_path, monkeypatch):
    target = tmp_path / "x" / "data"
    monkeypatch.setenv("PND_DATA_DIR", str(target))
    assert data_dir() == target and target.is_dir()


def test_data_dir_env_tilde_is_expanded(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("PND_DATA_DIR", "~/.akane")
    assert data_dir() == tmp_path / ".akane"


def test_get_persona_falls_back_to_defaults_without_config(tmp_path, monkeypatch):
    monkeypatch.setenv("PND_CONFIG_PATH", str(tmp_path / "missing.yaml"))
    get_persona.cache_clear()
    try:
        assert get_persona().name == "Dann"
    finally:
        get_persona.cache_clear()


def test_blank_persona_values_fall_back_to_defaults():
    p = persona_from_config({"persona": {"name": None, "wake_phrase": None, "data_dir": None}})
    assert (p.name, p.wake_phrase) == ("Dann", "ok Dann")
    assert p.data_dir == Path.home() / ".dann"


def test_theme_defaults_to_empty_and_reads_config():
    assert persona_from_config(None).theme == ""
    assert persona_from_config({"persona": {"theme": "rose"}}).theme == "rose"
