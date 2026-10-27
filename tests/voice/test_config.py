"""Unit tests for voice/config.py's load_config — specifically the path
resolution order (explicit arg > PND_CONFIG_PATH > DANN_CONFIG_PATH env var >
directory-math fallback) and the config.local.yaml overlay. This broke silently during the dann-of-thursday extraction
(every no-args caller resolved one directory too shallow once voice/ moved
into a runtime/ submodule) and nothing caught it because nothing exercised
it — see dann-of-thursday/docs/godot-integration-roadmap.md, Phase 2.
"""

import pytest

from voice.config import load_config


class TestLoadConfig:
    def test_explicit_path_used_when_given(self, tmp_path, monkeypatch):
        monkeypatch.delenv("PND_CONFIG_PATH", raising=False)
        monkeypatch.delenv("DANN_CONFIG_PATH", raising=False)
        cfg_file = tmp_path / "explicit.yaml"
        cfg_file.write_text("foo: bar\n")

        assert load_config(cfg_file) == {"foo": "bar"}

    def test_env_var_used_when_no_explicit_path_given(self, tmp_path, monkeypatch):
        cfg_file = tmp_path / "envconfig.yaml"
        cfg_file.write_text("hello: world\n")
        monkeypatch.delenv("PND_CONFIG_PATH", raising=False)
        monkeypatch.setenv("DANN_CONFIG_PATH", str(cfg_file))

        assert load_config() == {"hello": "world"}

    def test_explicit_path_overrides_env_var(self, tmp_path, monkeypatch):
        env_file = tmp_path / "env.yaml"
        env_file.write_text("source: env\n")
        explicit_file = tmp_path / "explicit.yaml"
        explicit_file.write_text("source: explicit\n")
        monkeypatch.setenv("DANN_CONFIG_PATH", str(env_file))

        assert load_config(explicit_file) == {"source": "explicit"}

    def test_missing_file_raises_with_a_helpful_message(self, tmp_path, monkeypatch):
        monkeypatch.delenv("PND_CONFIG_PATH", raising=False)
        monkeypatch.delenv("DANN_CONFIG_PATH", raising=False)
        missing = tmp_path / "does_not_exist.yaml"

        with pytest.raises(FileNotFoundError, match="PND_CONFIG_PATH"):
            load_config(missing)

    def test_pnd_config_path_wins_over_dann_config_path(self, tmp_path, monkeypatch):
        pnd = tmp_path / "pnd.yaml"
        pnd.write_text("source: pnd\n")
        dann = tmp_path / "dann.yaml"
        dann.write_text("source: dann\n")
        monkeypatch.setenv("PND_CONFIG_PATH", str(pnd))
        monkeypatch.setenv("DANN_CONFIG_PATH", str(dann))

        assert load_config() == {"source": "pnd"}

    def test_local_overlay_deep_merges(self, tmp_path, monkeypatch):
        monkeypatch.delenv("PND_CONFIG_PATH", raising=False)
        base = tmp_path / "config.yaml"
        base.write_text("ollama:\n  model: small\n  base_url: http://x\nagents: [a, b]\n")
        (tmp_path / "config.local.yaml").write_text("ollama:\n  model: big\nagents: [c]\n")

        assert load_config(base) == {
            "ollama": {"model": "big", "base_url": "http://x"},
            "agents": ["c"],
        }

    def test_empty_local_overlay_is_ignored(self, tmp_path):
        base = tmp_path / "config.yaml"
        base.write_text("a: 1\n")
        (tmp_path / "config.local.yaml").write_text("")

        assert load_config(base) == {"a": 1}

    def test_local_overlay_empty_section_does_not_wipe_base(self, tmp_path):
        base = tmp_path / "config.yaml"
        base.write_text("mcp:\n  servers: [a]\n")
        (tmp_path / "config.local.yaml").write_text("mcp:\n  # servers: [b]\n")

        assert load_config(base) == {"mcp": {"servers": ["a"]}}

    def test_local_overlay_that_is_not_a_mapping_raises_clearly(self, tmp_path):
        base = tmp_path / "config.yaml"
        base.write_text("a: 1\n")
        (tmp_path / "config.local.yaml").write_text("- a\n- b\n")

        with pytest.raises(ValueError, match="config.local.yaml"):
            load_config(base)
