"""`python -m integrations.job_search hunt` — run one hunt now (what
`akane hunt` and the nightly launchd job run). Always exits 0 once the
config loads: problems are written into the report instead."""

from __future__ import annotations

import sys
from datetime import date

from integrations.job_search.client import JobSearchApp
from integrations.job_search.hunt import run_hunt
from integrations.job_search.leads import LeadStore
from integrations.job_search.rules import http_status
from shared.claude_cli import run_claude
from shared.persona import data_dir
from voice.config import load_config


def main(argv: list[str]) -> int:
    if argv[:1] != ["hunt"]:
        print("usage: python -m integrations.job_search hunt", file=sys.stderr)
        return 2
    cfg = load_config()
    base_url = (cfg.get("job_search") or {}).get("base_url", "http://localhost:8080/api/v1")
    applications = data_dir() / "applications"
    result = run_hunt(cfg, app=JobSearchApp(base_url), store=LeadStore(applications / "leads.json"),
                      claude=run_claude, get_status=http_status, today=date.today().isoformat(),
                      reports_dir=applications / "reports")
    print(f"{len(result.added)} new lead(s) → {result.report_path}", flush=True)
    for n in result.notes:
        print(f"note: {n}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
