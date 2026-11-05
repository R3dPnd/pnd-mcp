"""integrations.job_search.client — talking to the pnd-job-search API."""

import pytest
import requests

from integrations.job_search.client import JobSearchApp, JobSearchUnavailable

BASE = "http://app/api/v1"


class FakeResponse:
    def __init__(self, status=200, payload=None):
        self.status_code = status
        self._payload = payload if payload is not None else {}

    def json(self):
        return self._payload


class FakeSession:
    """Records calls; returns canned responses keyed by (method, path)."""

    def __init__(self, routes=None, raise_on=None):
        self.routes = routes or {}
        self.raise_on = raise_on
        self.calls = []

    def request(self, method, url, params=None, timeout=None, **kw):
        path = url[len(BASE):]
        self.calls.append((method, path, params))
        if self.raise_on:
            raise self.raise_on
        return self.routes.get((method, path), FakeResponse(404, {"error": "not found"}))


def test_search_passes_query_location_and_remote():
    s = FakeSession({("GET", "/job-postings/search"): FakeResponse(200, {"postings": [{"id": "p1"}], "count": 1})})
    assert JobSearchApp(BASE, http=s).search("software engineer", "Tacoma, WA", remote=True) == [{"id": "p1"}]
    assert s.calls == [("GET", "/job-postings/search",
                        {"query": "software engineer", "location": "Tacoma, WA", "remote": "true"})]


def test_search_omits_remote_when_false():
    s = FakeSession({("GET", "/job-postings/search"): FakeResponse(200, {"postings": [], "count": 0})})
    JobSearchApp(BASE, http=s).search("dev")
    assert s.calls[0][2] == {"query": "dev"}


def test_active_resume_text_reads_the_active_one():
    s = FakeSession({
        ("GET", "/resumes"): FakeResponse(200, {"resumes": [{"id": "old", "is_active": False}, {"id": "r2", "is_active": True}], "count": 2}),
        ("GET", "/resumes/r2"): FakeResponse(200, {"id": "r2", "raw_text": "Preston Harms\nSoftware Engineer"}),
    })
    assert JobSearchApp(BASE, http=s).active_resume_text() == "Preston Harms\nSoftware Engineer"


def test_no_active_resume_is_empty_text():
    s = FakeSession({("GET", "/resumes"): FakeResponse(200, {"resumes": [], "count": 0})})
    assert JobSearchApp(BASE, http=s).active_resume_text() == ""


def test_track_not_applied_adds_query_param():
    s = FakeSession({("POST", "/job-postings/p1/track"): FakeResponse(201, {"id": "a1"})})
    assert JobSearchApp(BASE, http=s).track("p1", applied=False) == {"id": "a1"}
    assert s.calls == [("POST", "/job-postings/p1/track", {"applied": "false"})]


def test_dismiss_posts():
    s = FakeSession({("POST", "/job-postings/p1/dismiss"): FakeResponse(200, {})})
    JobSearchApp(BASE, http=s).dismiss("p1")
    assert s.calls[0][:2] == ("POST", "/job-postings/p1/dismiss")


def test_connection_error_raises_unavailable():
    s = FakeSession(raise_on=requests.ConnectionError("refused"))
    with pytest.raises(JobSearchUnavailable, match="not reachable"):
        JobSearchApp(BASE, http=s).search("dev")


def test_5xx_raises_unavailable_with_app_message():
    s = FakeSession({("GET", "/job-postings/search"):
                     FakeResponse(503, {"error": "job search is not configured: set JOBS_API_KEY"})})
    with pytest.raises(JobSearchUnavailable, match="set JOBS_API_KEY"):
        JobSearchApp(BASE, http=s).search("dev")


def test_healthy():
    assert JobSearchApp(BASE, http=FakeSession({("GET", "/health"): FakeResponse(200)})).healthy() is True
    assert JobSearchApp(BASE, http=FakeSession(raise_on=requests.ConnectionError())).healthy() is False


def test_unreachable_message_is_the_same_for_every_request():
    # A real ConnectionError's text includes the request path and query, so
    # each search used to produce a different note (review: 7 notes, not 1).
    class Varying(FakeSession):
        n = 0

        def request(self, method, url, **kw):
            Varying.n += 1
            raise requests.ConnectionError(f"Max retries exceeded with url: {url}?n={Varying.n}")

    app = JobSearchApp(BASE, http=Varying())
    messages = set()
    for q in ("a", "b"):
        with pytest.raises(JobSearchUnavailable) as e:
            app.search(q)
        messages.add(str(e.value))
    assert messages == {f"job search app not reachable at {BASE}"}
