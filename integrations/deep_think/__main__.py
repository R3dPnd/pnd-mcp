"""`python -m integrations.deep_think --stream-id ID --question TEXT` — run one
think_deeply job (spawned detached by claude_server.think_deeply)."""

from __future__ import annotations

import argparse
import sys

import requests

from integrations.deep_think import history_for, run
from shared.claude_cli import run_claude
from shared.persona import data_dir, get_persona
from voice.config import load_config


def _post(body: dict) -> bool:
    try:
        url = f"http://localhost:{get_persona().api_port}/api/v1/announce"
        return requests.post(url, json=body, timeout=10).status_code == 200
    except requests.RequestException:
        return False


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="deep_think")
    p.add_argument("--stream-id", default="")
    p.add_argument("--question", required=True)
    args = p.parse_args(argv)
    cfg = load_config()
    run(args.question, stream_id=args.stream_id, history=history_for(args.stream_id, data_dir()),
        location=(cfg.get("user") or {}).get("location", ""), claude=run_claude, post=_post)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
