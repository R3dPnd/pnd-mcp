"""Shared local-data helpers for the optional MCP modules.

Personal, non-git data (notes, cached OAuth tokens, etc.) lives in the
persona data dir (`persona.data_dir`, default ~/.dann — see shared/persona.py)
rather than inside the repo — the same reasoning that got
config.yaml untracked: this is per-machine state, not something that
belongs in git.
"""
import copy
import json
from pathlib import Path
from typing import Any

from shared.persona import data_dir


def data_home() -> Path:
    return data_dir()


# Pre-persona name, kept so existing imports keep working.
dann_home = data_home


def load_json(filename: str, default: Any) -> Any:
    """Returns a deep copy of *default* when the file is missing/corrupt —
    never the caller's own object. Without this, a caller that passes a
    shared module-level dict/list as *default* and then mutates the result
    in place (e.g. `data["items"].append(...)`) permanently pollutes that
    shared object for every future call across every data-dir location, not
    just the one it just wrote to."""
    path = data_home() / filename
    if not path.exists():
        return copy.deepcopy(default)
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return copy.deepcopy(default)


def save_json(filename: str, data: Any) -> None:
    path = data_home() / filename
    path.write_text(json.dumps(data, indent=2))
