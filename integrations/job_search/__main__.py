"""`python -m integrations.job_search hunt [--announce]` — run one hunt now.

`akane hunt` and the nightly launchd job run it plain; the morning report is
delivered later, when Akane is ready. "Find me jobs" (job_search_server's
start_hunt) adds --announce: when the hunt finishes, Akane says so and posts
the new leads — or, if she's down, it's queued for her next start.
Always exits 0 once the config loads: problems are written into the report.
"""

from __future__ import annotations

import json
import sys
from datetime import date

import requests

from integrations.job_search.client import JobSearchApp
from integrations.job_search.delivery import chat_text, pending_path, spoken_summary
from integrations.job_search.hunt import run_hunt
from integrations.job_search.leads import LeadStore
from integrations.job_search.lock import announce_request_path, lock_path, try_lock
from integrations.job_search.report import render_report
from integrations.job_search.rules import http_status
from shared.claude_cli import run_claude
from shared.persona import data_dir, get_persona
from voice.config import load_config

CHAT_TITLE = "Morning report"


def _announce(result, store: LeadStore, today: str) -> None:
    text = spoken_summary(result.added, result.notes, opening="Your job hunt is done.", period="")
    chat = chat_text(render_report(today, result.added, result.notes))
    url = f"http://localhost:{get_persona().api_port}/api/v1/announce"
    try:
        resp = requests.post(url, json={"text": text, "chat_title": CHAT_TITLE, "chat_text": chat}, timeout=10)
        if resp.status_code != 200:
            raise requests.RequestException(f"announce returned {resp.status_code}")
    except requests.RequestException:
        pending = pending_path(data_dir())
        queued = json.loads(pending.read_text()) if pending.is_file() else []
        pending.parent.mkdir(parents=True, exist_ok=True)
        pending.write_text(json.dumps(queued + [{"text": text, "chat": chat}], indent=2))
    # Shown either way: announced now, or queued to be announced at the next
    # start — the morning report mustn't read them again.
    for lead in result.added:
        store.set_status(lead.key, "shown")


def main(argv: list[str]) -> int:
    if argv[:1] != ["hunt"]:
        print("usage: python -m integrations.job_search hunt [--announce]", file=sys.stderr)
        return 2
    base = data_dir()
    lock = try_lock(lock_path(base))
    if lock is None:
        print("A hunt is already running.", flush=True)
        return 0
    try:
        cfg = load_config()
        base_url = (cfg.get("job_search") or {}).get("base_url", "http://localhost:8080/api/v1")
        applications = base / "applications"
        store = LeadStore(applications / "leads.json")
        today = date.today().isoformat()
        result = run_hunt(cfg, app=JobSearchApp(base_url), store=store, claude=run_claude,
                          get_status=http_status, today=today, reports_dir=applications / "reports")
        print(f"{len(result.added)} new lead(s) → {result.report_path}", flush=True)
        for n in result.notes:
            print(f"note: {n}", flush=True)
        request = announce_request_path(base)
        if "--announce" in argv[1:] or request.exists():
            request.unlink(missing_ok=True)
            _announce(result, store, today)
        return 0
    finally:
        lock.close()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
