"""HTTP client for pnd-job-search, the user's job-hunting app (Go + Postgres),
which Akane uses as its job engine: JSearch postings, the active resume,
applications, and resume tailoring. See akane's job-hunt design §7."""

from __future__ import annotations

from typing import Any

import requests


class JobSearchUnavailable(Exception):
    """The app couldn't do it: not running, or it answered with a 5xx (e.g.
    "job search is not configured: set JOBS_API_KEY")."""


class JobSearchApp:
    def __init__(self, base_url: str, http: requests.Session | None = None):
        self.base_url = base_url.rstrip("/")
        self.http = http or requests.Session()

    def _call(self, method: str, path: str, params: dict[str, str] | None = None, timeout: float = 60) -> Any:
        try:
            resp = self.http.request(method, f"{self.base_url}{path}", params=params, timeout=timeout)
        except requests.RequestException as e:
            # Fixed text, not str(e): that embeds the request URL, so every
            # search would add a different note to the report.
            raise JobSearchUnavailable(f"job search app not reachable at {self.base_url}") from e
        if resp.status_code >= 500:
            try:
                detail = resp.json().get("error") or ""
            except ValueError:
                detail = ""
            raise JobSearchUnavailable(detail or f"job search app error {resp.status_code}")
        if resp.status_code >= 400:
            raise JobSearchUnavailable(f"{method} {path} → {resp.status_code}")
        return resp.json()

    def healthy(self) -> bool:
        try:
            self._call("GET", "/health", timeout=3)
            return True
        except JobSearchUnavailable:
            return False

    def search(self, query: str, location: str = "", remote: bool = False) -> list[dict]:
        params = {"query": query}
        if location:
            params["location"] = location
        if remote:
            params["remote"] = "true"
        return self._call("GET", "/job-postings/search", params=params).get("postings") or []

    def active_resume_text(self) -> str:
        resumes = self._call("GET", "/resumes").get("resumes") or []
        active = next((r for r in resumes if r.get("is_active")), None)
        if active is None:
            return ""
        return self._call("GET", f"/resumes/{active['id']}").get("raw_text") or ""

    def dismiss(self, posting_id: str) -> None:
        self._call("POST", f"/job-postings/{posting_id}/dismiss")

    def track(self, posting_id: str, applied: bool) -> dict:
        params = None if applied else {"applied": "false"}
        return self._call("POST", f"/job-postings/{posting_id}/track", params=params)
