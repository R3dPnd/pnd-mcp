#!/usr/bin/env python3
"""MCP server: the job hunt's follow-up tools — the morning report, one lead,
dismiss / applied / status updates, and starting a hunt now. The engine is
pnd-job-search (PND_JOB_SEARCH_URL); leads and reports live under the persona
data dir (see integrations/job_search/).

Exposed tools:
  get_morning_report  — the latest report
  get_lead            — one lead by its number in the latest report
  dismiss_lead        — not interested
  mark_applied        — "I applied to 1": tracked in the app at stage Applied
  update_application  — "Acme rejected me", "interviewing with Acme", ...
  start_hunt          — run a hunt now; announced when done
"""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from integrations.job_search.client import JobSearchApp, JobSearchUnavailable
from integrations.job_search.delivery import chat_text
from integrations.job_search.leads import Lead, LeadStore
from shared.persona import data_dir

mcp = FastMCP("job_search")

APP_DOWN = "I couldn't reach your job search app — is it running? (akane jobs-app status)"
STATUSES = ("applied", "interviewing", "offer", "rejected", "closed")
_INTERVIEW_STAGES = ("phone screen", "technical interview", "final round")


def _app() -> JobSearchApp:
    return JobSearchApp(os.environ.get("PND_JOB_SEARCH_URL", "http://localhost:8080/api/v1"))


def _store(base: Path | None = None) -> LeadStore:
    return LeadStore((base or data_dir()) / "applications" / "leads.json")


def _missing(store: LeadStore, n: int) -> str:
    latest = store.latest_report_date()
    count = len(store.for_date(latest)) if latest else 0
    return f"There's no number {n} in the latest report (it has {count})."


def morning_report_text(base: Path) -> str:
    reports = sorted((base / "applications" / "reports").glob("*.md"))
    if not reports:
        return "No report yet — say 'find me jobs' to run a hunt."
    return chat_text(reports[-1].read_text())


def get_lead_text(store: LeadStore, n: int) -> str:
    lead = store.by_number(n)
    if lead is None:
        return _missing(store, n)
    pay = lead.pay or "pay not listed"
    return (f"Number {n}: {lead.title} at {lead.org} ({pay}). {lead.fit} "
            f"Suggestion: {lead.suggestion} Link: {lead.url}")


def dismiss(app: JobSearchApp, store: LeadStore, n: int) -> str:
    lead = store.by_number(n)
    if lead is None:
        return _missing(store, n)
    try:
        if lead.key.startswith("app:"):
            app.dismiss(lead.key[4:])
    except JobSearchUnavailable:
        return APP_DOWN
    store.set_status(lead.key, "dismissed")
    return f"Dismissed number {n}, {lead.org}."


def _stage_named(stages: list[dict], name: str) -> dict | None:
    return next((s for s in stages if s.get("name", "").lower() == name.lower()), None)


def mark_applied(app: JobSearchApp, store: LeadStore, n: int, today: str) -> str:
    lead = store.by_number(n)
    if lead is None:
        return _missing(store, n)
    try:
        if lead.key.startswith("app:"):
            application = app.track(lead.key[4:], applied=True)
        else:
            application = app.create_application(lead.org, lead.title, lead.url, today, "akane:gig")
        applied = _stage_named(app.stages(application["id"]), "Applied")
        if applied and application.get("current_stage_id") != applied["id"]:
            app.advance(application["id"], applied["id"])
    except JobSearchUnavailable:
        return APP_DOWN
    store.set_status(lead.key, "applied")
    return f"Marked number {n}, {lead.org}, as applied — it's in your tracker."


def update_application(app: JobSearchApp, company: str, status: str) -> str:
    status = status.strip().lower()
    if status not in STATUSES:
        return f"I can set an application to: {', '.join(STATUSES)}."
    try:
        matches = [a for a in app.list_applications() if company.lower() in (a.get("company") or "").lower()]
        if not matches:
            return f"I couldn't find an application for {company}."
        application = max(matches, key=lambda a: a.get("updated_at") or "")
        name = application.get("company", company)
        note = f" (picked {name}, the most recent of {len(matches)})" if len(matches) > 1 else ""
        if status == "closed":
            app.update_status(application["id"], "archived")
            return f"Archived your {name} application{note}."
        stages = app.stages(application["id"])
        if status == "interviewing":
            order = [s["id"] for s in stages]
            current = order.index(application["current_stage_id"]) if application.get("current_stage_id") in order else -1
            target = next((s for s in stages[current + 1:] if s["name"].lower() in _INTERVIEW_STAGES), None) \
                or _stage_named(stages, "Phone Screen")
        else:
            target = _stage_named(stages, status.capitalize())
        if target:
            app.advance(application["id"], target["id"])
        if status in ("offer", "rejected"):
            app.update_status(application["id"], status)
        where = target["name"] if target else status
        return f"Moved your {name} application to {where}{note}."
    except JobSearchUnavailable:
        return APP_DOWN


@mcp.tool()
def get_morning_report() -> str:
    """The latest job-hunt morning report: numbered leads with pay, fit and links."""
    return morning_report_text(data_dir())


@mcp.tool()
def get_lead(n: int) -> str:
    """Details of lead number n in the latest morning report."""
    return get_lead_text(_store(), n)


@mcp.tool()
def dismiss_lead(n: int) -> str:
    """Not interested in lead number n — it won't come back."""
    return dismiss(_app(), _store(), n)


@mcp.tool(name="mark_applied")
def mark_applied_tool(n: int) -> str:
    """The user applied to lead number n: track it in the job search app at stage Applied."""
    return mark_applied(_app(), _store(), n, date.today().isoformat())


@mcp.tool(name="update_application")
def update_application_tool(company: str, status: str) -> str:
    """Update a tracked application: status is applied, interviewing, offer, rejected or closed."""
    return update_application(_app(), company, status)


if __name__ == "__main__":
    mcp.run()
