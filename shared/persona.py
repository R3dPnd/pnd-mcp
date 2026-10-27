"""Persona identity — the one place the runtime learns who it's running as.

pnd-mcp started life inside dann-of-thursday, so "Dann", "ok Dann", ~/.dann
and ports 8000/3000 were hardcoded throughout. A persona repo now names
itself in config.yaml's `persona:` block; everything that used to hardcode
those values asks this module instead. The defaults are exactly the old
hardcoded values, so a config without a `persona:` block behaves as before.

MCP tool-servers run as subprocesses that don't inherit the parent's env
(the mcp stdio client passes only a small allowlist), so they can't find
config.yaml on their own — MCPManager injects the resolved data dir as
`PND_DATA_DIR`, which data_dir() checks first.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from voice.config import load_config

DATA_DIR_ENV = "PND_DATA_DIR"


@dataclass(frozen=True)
class Persona:
    name: str = "Dann"
    wake_phrase: str = "ok Dann"
    data_dir: Path = Path("~/.dann")
    api_port: int = 8000
    ui_port: int = 3000


def persona_from_config(cfg: dict[str, Any] | None) -> Persona:
    block = (cfg or {}).get("persona") or {}
    defaults = Persona()
    return Persona(
        name=block.get("name", defaults.name),
        wake_phrase=block.get("wake_phrase", defaults.wake_phrase),
        data_dir=Path(block.get("data_dir", defaults.data_dir)).expanduser(),
        api_port=int(block.get("api_port", defaults.api_port)),
        ui_port=int(block.get("ui_port", defaults.ui_port)),
    )


@lru_cache(maxsize=1)
def get_persona() -> Persona:
    try:
        cfg = load_config()
    except FileNotFoundError:
        cfg = None
    return persona_from_config(cfg)


def data_dir() -> Path:
    """The persona's personal, non-git data directory (notes, history, tokens),
    created on first use."""
    env = os.environ.get(DATA_DIR_ENV)
    path = Path(env).expanduser() if env else get_persona().data_dir
    path.mkdir(parents=True, exist_ok=True)
    return path
