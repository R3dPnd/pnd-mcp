"""Load and validate configuration."""

import os
from pathlib import Path
from typing import Any

import yaml


def load_config(path: Path | None = None) -> dict[str, Any]:
    """Load config from YAML file.

    This repo (pnd-mcp) has no config.yaml of its own — a persona repo
    supplies it and checks this repo out as a submodule (conventionally at
    `runtime/`), so "repo root" for config purposes is the *persona* repo's
    root, not this one. Resolution order when `path` isn't given:

    1. `DANN_CONFIG_PATH` env var — set this from the persona repo's own
       launcher (it knows exactly where its config.yaml lives regardless of
       what this repo is checked out as/where).
    2. `config.yaml` one directory above wherever this file lives — correct
       only under the `runtime/` convention above; a reasonable default for
       ad-hoc/direct runs, but don't rely on it from persona repo code.
    """
    if path is None:
        env_path = os.environ.get("DANN_CONFIG_PATH")
        path = Path(env_path) if env_path else Path(__file__).resolve().parent.parent.parent / "config.yaml"
    if not path.exists():
        raise FileNotFoundError(
            f"Config not found: {path}. Set DANN_CONFIG_PATH, or copy "
            f"config.example.yaml to config.yaml in the persona repo root."
        )
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)
