"""The morning report: Markdown at <data_dir>/applications/reports/<date>.md,
with front matter recording when it was delivered (so it's read once)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from integrations.job_search.leads import Lead


def delivered_at(report_path: Path) -> str:
    """The front matter's delivered_at value ("" if not delivered or no file)."""
    if not report_path.is_file():
        return ""
    for line in report_path.read_text().splitlines()[1:]:
        if line == "---":
            break
        if line.startswith("delivered_at:"):
            return line.split(":", 1)[1].strip()
    return ""


def _lead_section(lead: Lead) -> str:
    heading = f"## {lead.number}. {lead.title} — {lead.org}" + (" [gig]" if lead.kind == "gig" else "")
    where = ", ".join(p for p in (lead.location, "remote" if lead.remote else "") if p) or "location not listed"
    link = lead.url + (" (couldn't verify — site blocks bots)" if lead.link == "blocked" else "")
    return "\n".join([
        heading,
        f"- Pay: {lead.pay or 'pay not listed'}",
        f"- Where: {where}",
        f"- Score: {lead.score}",
        f"- Fit: {lead.fit}",
        f"- Suggestion: {lead.suggestion}",
        f"- Link: {link}",
    ])


def render_report(report_date: str, leads: list[Lead], notes: list[str], delivered: str = "") -> str:
    day = date.fromisoformat(report_date)
    parts = [
        f"---\nreport_date: {report_date}\ndelivered_at: {delivered}\n---",
        f"# Leads for {day.strftime('%a %b')} {day.day}",
    ]
    if notes:
        parts.append("\n".join(f"> {n}" for n in notes))
    parts += [_lead_section(l) for l in leads] if leads else ["No new leads tonight."]
    return "\n\n".join(parts) + "\n"
