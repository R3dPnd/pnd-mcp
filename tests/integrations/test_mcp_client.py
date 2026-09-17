"""Unit tests for MCPManager (integrations/client.py) — the tools:
allowlist filter and the follow_up chaining mechanism. Both were added to
close real gaps found while wiring up the Godot MCP module: godot-mcp
reports 173 tools (way past what the small router model should see at
once), and prompt-only "always call get_editor_errors after an edit"
turned out unreliable with that same model — see
dann-of-thursday/docs/godot-integration-roadmap.md for how each was found.

Neither test class touches the async stdio transport — _filter_tools is a
pure function, and call_tool_with_follow_ups only calls self.call_tool
(mocked here), which is the actual boundary MCPManager's own async
connection machinery sits behind.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

from integrations.client import MCPManager, _filter_tools


def _tool(name: str) -> SimpleNamespace:
    return SimpleNamespace(name=name)


# ── _filter_tools ──────────────────────────────────────────────────────────────

class TestFilterTools:
    def test_none_allowlist_returns_everything(self):
        tools = [_tool("a"), _tool("b"), _tool("c")]
        assert _filter_tools(tools, None) == tools

    def test_allowlist_keeps_only_matching_names(self):
        tools = [_tool("a"), _tool("b"), _tool("c")]
        result = _filter_tools(tools, ["a", "c"])
        assert [t.name for t in result] == ["a", "c"]

    def test_names_not_in_allowlist_are_dropped(self):
        tools = [_tool("get_project_info"), _tool("deploy_to_android"), _tool("create_script")]
        result = _filter_tools(tools, ["get_project_info", "create_script"])
        assert "deploy_to_android" not in [t.name for t in result]

    def test_allowlist_with_no_matches_returns_empty(self):
        assert _filter_tools([_tool("a"), _tool("b")], ["z"]) == []

    def test_empty_allowlist_returns_empty(self):
        assert _filter_tools([_tool("a"), _tool("b")], []) == []

    def test_result_order_follows_original_tools_not_allowlist(self):
        tools = [_tool("c"), _tool("a"), _tool("b")]
        result = _filter_tools(tools, ["b", "a"])
        assert [t.name for t in result] == ["a", "b"]


# ── call_tool_with_follow_ups ───────────────────────────────────────────────────

class TestCallToolWithFollowUps:
    def _manager(self, follow_up: dict[str, list[str]]) -> MCPManager:
        mgr = MCPManager()
        mgr._follow_up = follow_up
        return mgr

    def test_no_follow_up_configured_returns_just_the_primary_result(self):
        mgr = self._manager({})
        mgr.call_tool = MagicMock(return_value="primary result")

        result = mgr.call_tool_with_follow_ups("some_tool", {"a": 1})

        assert result == [("some_tool", "primary result")]
        mgr.call_tool.assert_called_once_with("some_tool", {"a": 1}, None)

    def test_single_follow_up_runs_immediately_after_primary(self):
        mgr = self._manager({"create_script": ["get_editor_errors"]})
        mgr.call_tool = MagicMock(side_effect=["created", "no errors"])

        result = mgr.call_tool_with_follow_ups("create_script", {"path": "x.gd"})

        assert result == [("create_script", "created"), ("get_editor_errors", "no errors")]
        assert mgr.call_tool.call_args_list[0].args == ("create_script", {"path": "x.gd"}, None)
        assert mgr.call_tool.call_args_list[1].args == ("get_editor_errors", {}, None)

    def test_multiple_follow_ups_all_run_in_configured_order(self):
        mgr = self._manager({"edit_script": ["get_editor_errors", "get_output_log"]})
        mgr.call_tool = MagicMock(side_effect=["edited", "no errors", "log output"])

        result = mgr.call_tool_with_follow_ups("edit_script", {})

        assert [name for name, _ in result] == ["edit_script", "get_editor_errors", "get_output_log"]

    def test_unrelated_tool_has_no_follow_up(self):
        mgr = self._manager({"create_script": ["get_editor_errors"]})
        mgr.call_tool = MagicMock(return_value="result")

        result = mgr.call_tool_with_follow_ups("get_scene_tree", {})

        assert result == [("get_scene_tree", "result")]

    def test_primary_exception_is_caught_and_reported_as_a_result_string(self):
        """Never raises — ollama.py's tool-round loop has no try/except
        around this call anymore; it relies on that."""
        mgr = self._manager({})
        mgr.call_tool = MagicMock(side_effect=RuntimeError("boom"))

        result = mgr.call_tool_with_follow_ups("bad_tool", {})

        assert len(result) == 1
        name, message = result[0]
        assert name == "bad_tool"
        assert "Error calling bad_tool" in message
        assert "boom" in message

    def test_follow_up_exception_does_not_hide_the_primary_result(self):
        mgr = self._manager({"create_script": ["get_editor_errors"]})
        mgr.call_tool = MagicMock(side_effect=["created", RuntimeError("editor unreachable")])

        result = mgr.call_tool_with_follow_ups("create_script", {})

        assert result[0] == ("create_script", "created")
        follow_up_name, follow_up_message = result[1]
        assert follow_up_name == "get_editor_errors"
        assert "Error calling get_editor_errors" in follow_up_message
        assert "editor unreachable" in follow_up_message

    def test_session_context_passed_through_to_every_call(self):
        mgr = self._manager({"create_script": ["get_editor_errors"]})
        mgr.call_tool = MagicMock(return_value="ok")
        ctx = {"focus_area": "godot"}

        mgr.call_tool_with_follow_ups("create_script", {}, ctx)

        for call in mgr.call_tool.call_args_list:
            assert call.args[2] == ctx
