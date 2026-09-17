"""Unit tests for the Claude Code MCP server tools."""

import os
import pytest
import requests
from pathlib import Path
from unittest.mock import patch, MagicMock


# ── _normalise ────────────────────────────────────────────────────────────────

class TestNormalise:
    @pytest.mark.parametrize("name, expected", [
        ("dev-diary",       "dev diary"),
        ("dev_diary",       "dev diary"),
        ("dann-of-thursday", "dann of thursday"),
        ("MyProject",       "myproject"),
        ("already fine",    "already fine"),
    ])
    def test_normalises_correctly(self, name, expected):
        from integrations.servers.claude_code_server import _normalise
        assert _normalise(name) == expected


# ── find_projects ────────────────────────────────────────────────────────────

class TestFindProjects:
    def test_discovers_git_repo(self, tmp_path):
        repo = tmp_path / "my-project"
        repo.mkdir()
        (repo / ".git").mkdir()

        with patch("integrations.servers.claude_code_server._SEARCH_ROOTS", [tmp_path]), \
             patch("integrations.servers.claude_code_server._projects_cache", None):
            import integrations.servers.claude_code_server as srv
            srv._projects_cache = None
            projects = srv.find_projects()

        names = [p["name"] for p in projects]
        assert "my-project" in names

    def test_skips_venv_directories(self, tmp_path):
        repo = tmp_path / "real-project"
        repo.mkdir()
        (repo / ".git").mkdir()

        venv = tmp_path / ".venv"
        venv.mkdir()
        fake_repo = venv / "fake-project"
        fake_repo.mkdir()
        (fake_repo / ".git").mkdir()

        with patch("integrations.servers.claude_code_server._SEARCH_ROOTS", [tmp_path]), \
             patch("integrations.servers.claude_code_server._projects_cache", None):
            import integrations.servers.claude_code_server as srv
            srv._projects_cache = None
            projects = srv.find_projects()

        names = [p["name"] for p in projects]
        assert "fake-project" not in names
        assert "real-project" in names

    def test_returns_sorted_by_name(self, tmp_path):
        for name in ["zebra-project", "alpha-project", "middle-project"]:
            repo = tmp_path / name
            repo.mkdir()
            (repo / ".git").mkdir()

        with patch("integrations.servers.claude_code_server._SEARCH_ROOTS", [tmp_path]), \
             patch("integrations.servers.claude_code_server._projects_cache", None):
            import integrations.servers.claude_code_server as srv
            srv._projects_cache = None
            projects = srv.find_projects()

        names = [p["name"] for p in projects]
        assert names == sorted(names, key=str.lower)

    def test_uses_cache_on_second_call(self, tmp_path):
        cached = [{"name": "cached-project", "path": str(tmp_path)}]

        with patch("integrations.servers.claude_code_server._projects_cache", cached):
            import integrations.servers.claude_code_server as srv
            result = srv.find_projects()

        assert result is cached

    def test_missing_root_directory_returns_empty(self, tmp_path):
        missing = tmp_path / "nonexistent"

        with patch("integrations.servers.claude_code_server._SEARCH_ROOTS", [missing]), \
             patch("integrations.servers.claude_code_server._projects_cache", None):
            import integrations.servers.claude_code_server as srv
            srv._projects_cache = None
            projects = srv.find_projects()

        assert projects == []


# ── resolve_project ──────────────────────────────────────────────────────────

class TestResolveProject:
    def _make_projects(self):
        return [
            {"name": "dev-diary",        "path": "/repos/dev-diary"},
            {"name": "dann-of-thursday", "path": "/repos/dann-of-thursday"},
            {"name": "fieldwatch-api",   "path": "/repos/fieldwatch-api"},
        ]

    def test_exact_normalised_match(self):
        projects = self._make_projects()
        with patch("integrations.servers.claude_code_server.find_projects",
                   return_value=projects):
            from integrations.servers.claude_code_server import resolve_project
            result = resolve_project("dev diary")
        assert result["name"] == "dev-diary"

    def test_partial_match_fallback(self):
        projects = self._make_projects()
        with patch("integrations.servers.claude_code_server.find_projects",
                   return_value=projects):
            from integrations.servers.claude_code_server import resolve_project
            result = resolve_project("fieldwatch")
        assert result["name"] == "fieldwatch-api"

    def test_unknown_project_returns_none(self):
        projects = self._make_projects()
        with patch("integrations.servers.claude_code_server.find_projects",
                   return_value=projects):
            from integrations.servers.claude_code_server import resolve_project
            result = resolve_project("nonexistent-repo")
        assert result is None

    def test_hyphens_in_query_normalised(self):
        projects = self._make_projects()
        with patch("integrations.servers.claude_code_server.find_projects",
                   return_value=projects):
            from integrations.servers.claude_code_server import resolve_project
            result = resolve_project("dann-of-thursday")
        assert result["name"] == "dann-of-thursday"


# ── list_projects ─────────────────────────────────────────────────────────────

class TestListProjects:
    def test_lists_all_projects(self):
        projects = [
            {"name": "alpha", "path": "/repos/alpha"},
            {"name": "beta",  "path": "/repos/beta"},
        ]
        with patch("integrations.servers.claude_code_server.find_projects",
                   return_value=projects):
            from integrations.servers.claude_code_server import list_projects
            result = list_projects()
        assert "alpha" in result
        assert "beta" in result

    def test_empty_returns_no_projects_message(self):
        with patch("integrations.servers.claude_code_server.find_projects",
                   return_value=[]):
            from integrations.servers.claude_code_server import list_projects
            result = list_projects()
        assert "No projects found" in result


# ── ask_claude_code ───────────────────────────────────────────────────────────

class TestAskClaudeCode:
    """ask_claude_code is now a one-line delegate to open_claude_code (see
    its own docstring: the answer goes to the dashboard's watchable
    terminal, not returned directly here) — it used to run `claude`
    non-interactively via subprocess.run and capture stdout, but that
    implementation is gone. The tests below used to assert against that
    old behavior and silently broke when it changed; see TestOpenClaudeCode
    for coverage of what actually happens now."""

    def test_delegates_to_open_claude_code_with_the_same_arguments(self):
        with patch("integrations.servers.claude_code_server.open_claude_code",
                   return_value="Claude Code (dev-diary): It's a diary app.") as mock_open:
            from integrations.servers.claude_code_server import ask_claude_code
            result = ask_claude_code("dev diary", "Summarise this project", "coding")

        mock_open.assert_called_once_with("dev diary", "Summarise this project", "coding")
        assert result == "Claude Code (dev-diary): It's a diary app."


class TestOpenClaudeCode:
    def test_unknown_project_without_focus_area_lists_available_projects(self):
        with patch("integrations.servers.claude_code_server.resolve_project",
                   return_value=None), \
             patch("integrations.servers.claude_code_server.find_projects",
                   return_value=[{"name": "dev-diary"}, {"name": "pnd-mcp"}]):
            from integrations.servers.claude_code_server import open_claude_code
            result = open_claude_code("ghost-project", "Do something")

        assert "not found" in result.lower()
        assert "dev-diary" in result
        assert "pnd-mcp" in result

    def test_unknown_project_with_focus_area_falls_back_to_open_terminal(self):
        """No git repo matched, but the caller told us which focus area
        this belongs to — that's not a codebase, so hand off to
        open_terminal instead of just reporting 'not found'."""
        with patch("integrations.servers.claude_code_server.resolve_project",
                   return_value=None), \
             patch("integrations.servers.claude_code_server.open_terminal",
                   return_value="terminal opened") as mock_terminal:
            from integrations.servers.claude_code_server import open_claude_code
            result = open_claude_code("not-a-project", "chat about the garden", "gardening")

        mock_terminal.assert_called_once_with(task="chat about the garden", focus_area="gardening")
        assert result == "terminal opened"

    def test_known_project_posts_to_dashboard_terminal_api(self):
        project = {"name": "dev-diary", "path": "/repos/dev-diary"}
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"output": "It's a diary app.", "settled": True, "continued": False}

        with patch("integrations.servers.claude_code_server.resolve_project",
                   return_value=project), \
             patch("integrations.servers.claude_code_server.requests.post",
                   return_value=mock_resp) as mock_post:
            from integrations.servers.claude_code_server import open_claude_code
            result = open_claude_code("dev diary", "Summarise this project")

        assert mock_post.call_args.args[0].endswith("/api/v1/terminals/claude-code")
        assert mock_post.call_args.kwargs["json"]["project_name"] == "dev-diary"
        assert result == "Claude Code (dev-diary): It's a diary app."

    def test_dashboard_unreachable_falls_back_to_native_terminal(self):
        project = {"name": "dev-diary", "path": "/repos/dev-diary"}
        mock_osa_result = MagicMock(returncode=0, stderr="")

        with patch("integrations.servers.claude_code_server.resolve_project",
                   return_value=project), \
             patch("integrations.servers.claude_code_server.requests.post",
                   side_effect=requests.RequestException("connection refused")), \
             patch("integrations.servers.claude_code_server.subprocess.run",
                   return_value=mock_osa_result):
            from integrations.servers.claude_code_server import open_claude_code
            result = open_claude_code("dev diary", "Summarise")

        assert "Opened Claude Code in 'dev-diary'" in result
        assert "Summarise" in result

    def test_native_terminal_osascript_failure_is_reported(self):
        project = {"name": "dev-diary", "path": "/repos/dev-diary"}
        mock_osa_result = MagicMock(returncode=1, stderr="osascript: permission denied")

        with patch("integrations.servers.claude_code_server.resolve_project",
                   return_value=project), \
             patch("integrations.servers.claude_code_server.requests.post",
                   side_effect=requests.RequestException("connection refused")), \
             patch("integrations.servers.claude_code_server.subprocess.run",
                   return_value=mock_osa_result):
            from integrations.servers.claude_code_server import open_claude_code
            result = open_claude_code("dev diary", "")

        assert "failed to open terminal" in result.lower()
        assert "permission denied" in result.lower()
