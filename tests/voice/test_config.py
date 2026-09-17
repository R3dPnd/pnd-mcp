"""Unit tests for voice/config.py's load_config — specifically the path
resolution order (explicit arg > DANN_CONFIG_PATH env var > directory-math
fallback). This broke silently during the dann-of-thursday extraction
(every no-args caller resolved one directory too shallow once voice/ moved
into a runtime/ submodule) and nothing caught it because nothing exercised
it — see dann-of-thursday/docs/godot-integration-roadmap.md, Phase 2.
"""

import pytest

from voice.config import load_config


class TestLoadConfig:
    def test_explicit_path_used_when_given(self, tmp_path, monkeypatch):
        monkeypatch.delenv("DANN_CONFIG_PATH", raising=False)
        cfg_file = tmp_path / "explicit.yaml"
        cfg_file.write_text("foo: bar\n")

        assert load_config(cfg_file) == {"foo": "bar"}

    def test_env_var_used_when_no_explicit_path_given(self, tmp_path, monkeypatch):
        cfg_file = tmp_path / "envconfig.yaml"
        cfg_file.write_text("hello: world\n")
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
        monkeypatch.delenv("DANN_CONFIG_PATH", raising=False)
        missing = tmp_path / "does_not_exist.yaml"

        with pytest.raises(FileNotFoundError, match="DANN_CONFIG_PATH"):
            load_config(missing)
