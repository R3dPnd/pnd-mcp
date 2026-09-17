"""MCP client manager — bridges async MCP SDK to sync orchestrator.

Each entry in config.yaml's mcp.servers list is a module with one of two
lifecycles:

  always_on: true    Connected immediately in start() and stays up for the
                      whole session — for modules used on nearly every turn
                      (e.g. the "projects"/Claude Code bridge). This is the
                      "easy switch": flip the flag, restart Dann.
  always_on: false    (default) Registered but NOT started. Three synthetic
                      meta-tools (list_modules / enable_module /
                      disable_module) are exposed instead, so the LLM
                      starts a module's process only when a turn actually
                      needs it, and can stop it again afterwards. This is
                      what keeps both the tool list sent to Ollama and the
                      process count small as more modules get added.

An entry can also set `tools: [name, ...]` (expose only that subset instead
of everything the server reports — see _connect_one) and/or
`follow_up: {trigger_tool: [tool, ...]}` (after *trigger_tool* runs, also
run each listed tool automatically, no extra model round required — see
call_tool_with_follow_ups). Both are optional; omitting either keeps the
simplest behavior (expose everything, chain nothing).
"""

import asyncio
import logging
import threading
from typing import Any

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

_log = logging.getLogger(__name__)

_META_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "list_modules",
            "description": (
                "List optional Dann modules and whether each is active or "
                "just available. Call this when the user asks what you can "
                "do, or if you're unsure whether a module is already on."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "enable_module",
            "description": (
                "Start an optional module so its tools become available. "
                "Call this the first time a turn needs a tool from a module "
                "that isn't active yet — its real tools appear right after."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "module": {
                        "type": "string",
                        "description": "Module name, e.g. 'schedule', 'notes', 'system'.",
                    }
                },
                "required": ["module"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "disable_module",
            "description": "Stop an active optional module to free resources once it's no longer needed this session.",
            "parameters": {
                "type": "object",
                "properties": {"module": {"type": "string"}},
                "required": ["module"],
            },
        },
    },
]
_META_TOOL_NAMES = {t["function"]["name"] for t in _META_TOOLS}

# Tools that declare a `focus_area` parameter meant to be supplied by the
# caller (see call_tool's session_context), not filled in by the LLM.
_FOCUS_AREA_AWARE_TOOLS = {"open_claude_code", "ask_claude_code", "open_terminal", "save_focus_area_note"}


def _filter_tools(tools: list[Any], allowed: list[str] | None) -> list[Any]:
    """Return only the tools in *allowed* (matched by .name), or every tool
    if *allowed* is None. A pure function (no I/O, no session) so the
    mcp.servers[].tools allowlist behavior is unit-testable without mocking
    the async stdio transport — see _connect_one, the only caller."""
    if allowed is None:
        return list(tools)
    allowed_set = set(allowed)
    return [t for t in tools if t.name in allowed_set]


class MCPManager:
    """Maintains MCP server connections in a background event loop.

    All public methods are synchronous so the rest of the (sync) codebase
    can call them directly.  Internally, coroutines are dispatched to a
    dedicated asyncio loop running on a daemon thread.
    """

    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._configs: dict[str, dict[str, Any]] = {}   # name -> full config
        # name -> (owning task, its stop event). stdio_client's cancel scope
        # (anyio) must be entered and exited in the *same* asyncio Task, so
        # each connected server gets one long-lived task that opens its own
        # stdio_client/ClientSession and only tears them down when its own
        # stop event fires — connect and disconnect are just signals to it,
        # not separate enter/exit calls from different tasks.
        self._server_tasks: dict[str, tuple[asyncio.Task, asyncio.Event]] = {}
        self._sessions: dict[str, ClientSession] = {}
        self._tool_map: dict[str, str] = {}              # tool_name -> server_name
        self._tools: list[dict[str, Any]] = []            # Ollama-formatted tool defs, mutated in place
        self._follow_up: dict[str, list[str]] = {}        # tool_name -> [tool names to auto-call right after]
        self._start_lock = threading.Lock()
        self._started = False

    # ------------------------------------------------------------------
    # Sync public API
    # ------------------------------------------------------------------

    def start(self, server_configs: list[dict[str, Any]]) -> None:
        """Start background loop, connect always_on servers, register the rest.

        Idempotent — safe to call more than once (e.g. once from the voice
        orchestrator and once from the FastAPI app when both are using the
        shared manager from get_shared_manager()); only the first call does
        anything.
        """
        with self._start_lock:
            if self._started:
                return
            self._started = True

        self._thread.start()
        for cfg in server_configs:
            self._configs[cfg["name"]] = cfg
            for trigger, follow_ups in (cfg.get("follow_up") or {}).items():
                self._follow_up.setdefault(trigger, []).extend(follow_ups)

        always_on = [cfg for cfg in server_configs if cfg.get("always_on")]
        on_demand = [cfg for cfg in server_configs if not cfg.get("always_on")]

        for cfg in always_on:
            try:
                self._run(self._connect_one(cfg))
            except Exception:
                pass  # already logged in _connect_one; one bad always_on server shouldn't block startup

        if on_demand:
            self._tools.extend(_META_TOOLS)

    def stop(self) -> None:
        """Disconnect all servers and tear down the event loop."""
        for name in list(self._server_tasks):
            try:
                self._run(self._disconnect_one(name))
            except Exception:
                pass
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=5)

    @property
    def started(self) -> bool:
        return self._started

    @property
    def tools(self) -> list[dict[str, Any]]:
        """Ollama-formatted tool definitions — always_on tools, meta-tools (if
        any on-demand modules are configured), and whatever's currently
        enabled on demand. Returns the live list; enabling a module mid-turn
        is visible to the caller immediately since this isn't copied."""
        return self._tools

    def list_modules(self) -> list[dict[str, Any]]:
        """Structured module status for the dashboard — one entry per
        configured MCP server with its always_on flag and whether it's
        currently connected (always_on modules are connected in start() and
        read back as enabled here too)."""
        return [
            {
                "name": name,
                "description": cfg.get("description", ""),
                "always_on": bool(cfg.get("always_on")),
                "enabled": name in self._sessions,
            }
            for name, cfg in self._configs.items()
        ]

    def enable_module(self, name: str) -> None:
        """Synchronous wrapper for the dashboard's enable endpoint — same
        connect path the enable_module LLM tool uses."""
        cfg = self._configs.get(name)
        if cfg is None:
            raise KeyError(name)
        if cfg.get("always_on") or name in self._sessions:
            return
        self._run(self._connect_one(cfg))

    def disable_module(self, name: str) -> None:
        """Synchronous wrapper for the dashboard's disable endpoint."""
        cfg = self._configs.get(name)
        if cfg is None:
            raise KeyError(name)
        if cfg.get("always_on") or name not in self._sessions:
            return
        self._run(self._disconnect_one(name))

    def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        session_context: dict[str, Any] | None = None,
    ) -> str:
        """Execute a tool — routed to the owning MCP server, or handled
        locally if it's one of the module-management meta-tools.

        *session_context* carries caller-known facts the LLM shouldn't be
        trusted to fill in itself (e.g. which focus area this turn's work
        stream belongs to) — forced into the call's arguments for the tools
        that declare a matching parameter, overriding whatever (if anything)
        the model supplied for it. Not merged in generally: an unexpected
        argument would fail a tool that doesn't declare it."""
        if tool_name in _META_TOOL_NAMES:
            return self._run(self._handle_meta_tool(tool_name, arguments))
        if tool_name in _FOCUS_AREA_AWARE_TOOLS and session_context and session_context.get("focus_area"):
            arguments = {**arguments, "focus_area": session_context["focus_area"]}
        return self._run(self._async_call_tool(tool_name, arguments))

    def call_tool_with_follow_ups(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        session_context: dict[str, Any] | None = None,
    ) -> list[tuple[str, str]]:
        """Like call_tool, but also runs any tools a server config declared
        as a follow_up for *tool_name* (see mcp.servers[].follow_up in
        config.yaml) — deterministically, not left to the calling LLM's own
        judgment to remember. Small/fast router models are unreliable at
        "always call Y after X" instructions given only in a tool's prompt
        description; this makes the chain happen in code instead. A
        follow-up's own failure doesn't hide the primary call's result —
        each is caught and reported independently.

        Returns [(tool_name, result_str), ...], primary call first, in the
        same order every result would otherwise be appended to the LLM's
        message history for this round.
        """
        try:
            primary_result = self.call_tool(tool_name, arguments, session_context)
        except Exception as exc:
            primary_result = f"Error calling {tool_name}: {exc}"
        results = [(tool_name, primary_result)]
        for follow_up_name in self._follow_up.get(tool_name, []):
            try:
                results.append((follow_up_name, self.call_tool(follow_up_name, {}, session_context)))
            except Exception as exc:
                results.append((follow_up_name, f"Error calling {follow_up_name}: {exc}"))
        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run(self, coro: Any, timeout: float = 30) -> Any:
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=timeout)

    async def _server_owner_task(
        self, cfg: dict[str, Any], ready: asyncio.Future, stop: asyncio.Event
    ) -> None:
        """Owns one server's stdio_client/ClientSession for their whole
        lifetime — opened and closed within this single task, as anyio's
        cancel scopes require. Resolves *ready* once connected (or with the
        connect exception), then just waits for *stop* before letting the
        `async with` blocks close themselves."""
        name = cfg["name"]
        try:
            params = StdioServerParameters(
                command=cfg["command"],
                args=cfg.get("args", []),
                env=cfg.get("env"),
            )
            async with stdio_client(params) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    tools_result = await session.list_tools()
                    if not ready.done():
                        ready.set_result((session, tools_result.tools))
                    await stop.wait()
        except Exception as exc:
            if not ready.done():
                ready.set_exception(exc)
            else:
                print(f"[mcp] '{name}' server task error: {exc}", flush=True)
        finally:
            self._server_tasks.pop(name, None)

    async def _connect_one(self, cfg: dict[str, Any]) -> None:
        name = cfg["name"]
        if name in self._sessions:
            return

        ready: asyncio.Future = self._loop.create_future()
        stop = asyncio.Event()
        task = self._loop.create_task(self._server_owner_task(cfg, ready, stop))
        self._server_tasks[name] = (task, stop)

        try:
            session, tools = await ready
        except Exception as exc:
            print(f"[mcp] Failed to connect to '{name}': {exc}", flush=True)
            raise

        # Optional allowlist (cfg["tools"]) — without it, every tool the
        # server reports gets exposed, which is fine for a small module but
        # dumps the server's *entire* catalog into the LLM's context on
        # enable_module otherwise (e.g. a 173-tool server). None (the
        # default) keeps prior behavior: expose everything.
        exposed_tools = _filter_tools(tools, cfg.get("tools"))
        for tool in exposed_tools:
            self._tool_map[tool.name] = name
            self._tools.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": tool.inputSchema,
                },
            })
        self._sessions[name] = session
        print(f"[mcp] Connected to '{name}' — {len(exposed_tools)}/{len(tools)} tool(s) exposed", flush=True)

    async def _disconnect_one(self, name: str) -> None:
        self._sessions.pop(name, None)
        removed = {tn for tn, sn in self._tool_map.items() if sn == name}
        for tn in removed:
            del self._tool_map[tn]
        self._tools[:] = [t for t in self._tools if t["function"]["name"] not in removed]

        entry = self._server_tasks.get(name)
        if entry:
            task, stop = entry
            stop.set()
            try:
                await asyncio.wait_for(task, timeout=5)
            except Exception:
                pass
        print(f"[mcp] Disconnected '{name}'", flush=True)

    async def _handle_meta_tool(self, name: str, args: dict[str, Any]) -> str:
        if name == "list_modules":
            lines = []
            for mod_name, cfg in self._configs.items():
                if cfg.get("always_on"):
                    continue  # not toggleable at runtime, don't clutter the list
                status = "active" if mod_name in self._sessions else "available"
                lines.append(f"- {mod_name} ({status}): {cfg.get('description', '')}")
            return "Optional modules:\n" + "\n".join(lines) if lines else "No optional modules configured."

        module = args.get("module", "")
        cfg = self._configs.get(module)
        if not cfg:
            known = ", ".join(n for n, c in self._configs.items() if not c.get("always_on"))
            return f"Unknown module '{module}'. Available: {known or 'none'}"
        if cfg.get("always_on"):
            return f"'{module}' is always on, nothing to do."

        if name == "enable_module":
            if module in self._sessions:
                return f"'{module}' is already active."
            try:
                await self._connect_one(cfg)
            except Exception as exc:
                return f"Failed to start '{module}': {exc}"
            new_tools = sorted(tn for tn, sn in self._tool_map.items() if sn == module)
            return f"'{module}' is now active. New tools available: {', '.join(new_tools)}"

        if name == "disable_module":
            if module not in self._sessions:
                return f"'{module}' isn't active."
            await self._disconnect_one(module)
            return f"'{module}' stopped."

        return f"Unknown meta tool '{name}'"

    async def _async_call_tool(self, tool_name: str, arguments: dict[str, Any]) -> str:
        server_name = self._tool_map.get(tool_name)
        if not server_name:
            raise ValueError(f"Unknown MCP tool: {tool_name}")
        session = self._sessions[server_name]
        result = await session.call_tool(tool_name, arguments)
        parts = []
        for content in result.content:
            if hasattr(content, "text"):
                parts.append(content.text)
            else:
                parts.append(str(content))
        return "\n".join(parts) if parts else ""


# ── Process-wide shared instance ────────────────────────────────────────────
#
# Both the voice orchestrator and text-chat work streams (app/services/
# chat_service.py) need the same MCP tool set and module state — one set of
# server processes, not one per consumer. get_shared_manager() returns the
# same MCPManager regardless of caller; start() is idempotent so whichever
# caller gets there first actually starts it.

_shared_manager: "MCPManager | None" = None
_shared_manager_lock = threading.Lock()


def get_shared_manager() -> "MCPManager":
    global _shared_manager
    with _shared_manager_lock:
        if _shared_manager is None:
            _shared_manager = MCPManager()
        return _shared_manager
