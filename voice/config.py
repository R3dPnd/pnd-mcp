"""Load and validate configuration."""

import os
from pathlib import Path
from typing import Any

import yaml

# Machine-specific overrides (model sizes, audio devices, absolute paths) live
# in this gitignored file next to config.yaml, so moving a persona to another
# machine is a matter of writing a new overlay rather than editing tracked config.
LOCAL_OVERLAY_NAME = "config.local.yaml"


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Return a new dict: *override* merged over *base*. Nested dicts merge
    key-by-key; lists and scalars in *override* replace *base*'s outright
    (merging list items, e.g. two `agents:` lists, has no obvious meaning).
    A None in *override* means "not set" — a section header whose children
    are all commented out parses as None and mustn't wipe the base section."""
    merged = dict(base)
    for key, value in override.items():
        if value is None:
            continue
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(path: Path | None = None) -> dict[str, Any]:
    """Load config from YAML file.

    This repo (pnd-mcp) has no config.yaml of its own — a persona repo
    supplies it and checks this repo out as a submodule (conventionally at
    `runtime/`), so "repo root" for config purposes is the *persona* repo's
    root, not this one. Resolution order when `path` isn't given:

    1. `PND_CONFIG_PATH` env var — set this from the persona repo's own
       launcher (it knows exactly where its config.yaml lives regardless of
       what this repo is checked out as/where).
    2. `DANN_CONFIG_PATH` — the pre-rename name of the same variable, still
       honoured so older launchers keep working.
    3. `config.yaml` one directory above wherever this file lives — correct
       only under the `runtime/` convention above; a reasonable default for
       ad-hoc/direct runs, but don't rely on it from persona repo code.

    If a `config.local.yaml` sits next to the resolved file, it's deep-merged
    over it (see deep_merge).
    """
    if path is None:
        env_path = os.environ.get("PND_CONFIG_PATH") or os.environ.get("DANN_CONFIG_PATH")
        path = Path(env_path) if env_path else Path(__file__).resolve().parent.parent.parent / "config.yaml"
    if not path.exists():
        raise FileNotFoundError(
            f"Config not found: {path}. Set PND_CONFIG_PATH, or copy "
            f"config.example.yaml to config.yaml in the persona repo root."
        )
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    overlay_path = path.parent / LOCAL_OVERLAY_NAME
    if overlay_path.exists() and overlay_path != path:
        with open(overlay_path, encoding="utf-8") as f:
            overlay = yaml.safe_load(f) or {}
        if not isinstance(overlay, dict):
            raise ValueError(f"{overlay_path} must be a YAML mapping of config sections to override.")
        cfg = deep_merge(cfg, overlay)
    return cfg
