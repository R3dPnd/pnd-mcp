# pnd-mcp — Claude Code Context

## What this is

The shared runtime for local-first AI agent personas: voice pipeline (wake word → STT →
LLM routing → TTS), an MCP client + a library of MCP tool-servers, and a FastAPI + React
dashboard that mirrors pipeline state live. Extracted from
[dann-of-thursday](https://github.com/R3dPnd/dann-of-thursday) so it can be reused by
other personas without forking that repo — see this repo's README for the extraction
rationale.

This repo does **not** contain a persona. It has no `config.yaml`, no system prompt, no
`dann.py`-equivalent entrypoint. A persona repo depends on this one (as a git submodule,
conventionally mounted at `runtime/`) and supplies:

- `config.yaml` — routing/system prompt, which MCP modules + focus areas are enabled,
  model/voice choices, absolute/relative paths as needed.
- Its own persona-specific MCP tool-servers, registered into `mcp.servers` alongside the
  ones here.
- A launcher (like `dann-of-thursday`'s `dann.py`) that runs this repo's `app.main:app`
  and `ui/` with `cwd` set to wherever this submodule lives, so `config.yaml`'s relative
  paths (`models/...`, `../.venv/bin/python` for MCP subprocess `command:` fields) resolve
  correctly.

## Directory layout

```
voice/          Voice pipeline (wake word → STT → LLM → TTS)
integrations/   MCP client + tool-server modules:
                  claude_code_server — project discovery + Claude Code session bridge
                  devteam_server     — background multi-phase Claude Code pipelines (builds on claude_code_server)
                  schedule, notes, gardening, bjj, system, focus_areas — general-purpose personal-assistant tools
shared/         Cross-cutting code used by both voice/ and app/ (agent routing config, restart)
app/            FastAPI backend + API (serves dashboard state, REST, WebSocket)
ui/             React + Tailwind dashboard (Vite dev server / optional Electron)
models/         Wake word models, Piper voice, openwakeword + piper-sample-generator submodules
scripts/        Guided setup (scripts/setup.sh), workstation bootstrap, wake-word training tooling
deploy/         Cloudflare Tunnel + launchd templates for remote access
docs/           Design/tech-spec/UI-spec docs and setup notes
```

## Key entry points

Run these from a *consuming* repo with this checked out at e.g. `runtime/`, using that
repo's shared venv and `cwd=runtime/`:

| What | Command |
|------|---------|
| Voice agent (full) | `.venv/bin/python -m voice.main` |
| Backend only (no mic) | `NO_VOICE=1 .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000` |
| UI dev server | `cd ui && npm run dev` (port 3000) |
| Standalone desktop app | `cd ui && npm run electron:start` — spawns its own backend, no browser tab, no Vite dev server needed |

## Architecture

```
wake word (Picovoice / openwakeword)
  → voice/orchestrator.py  ← core pipeline, emits events via voice/event_bus.py
  → voice/stt/whisper.py   ← faster-whisper transcription
  → voice/llm/ollama.py    ← Ollama LLM (local models)
  → voice/tts/piper.py     ← Piper TTS synthesis
  → voice/audio/playback.py

integrations/client.py    MCPManager — shared by voice/orchestrator.py and
                           app/services/chat_service.py (one set of MCP server
                           processes, not one per consumer)

app/main.py               FastAPI
  app/api/v1/endpoints/    state, events (WS), logs, metrics, projects,
                           terminals, runs, notes, prompt_builder, voice, chat,
                           devteam, system, resources, tools
  app/services/            terminal_service, run_service, chat_service,
                           system_service (host memory/CPU/GPU, Ollama's
                           loaded model, turn latency — /resources/*), etc.

ui/src/                    React dashboard (port 3000 dev / served from FastAPI prod)
ui/electron/                Standalone desktop wrapper — spawns its own backend
                           (see main.cjs's startBackend()) rather than needing a
                           browser tab or a separately-started server
```

## System panel (`/resources/status`, `/resources/turns`)

Host memory/CPU (`psutil`), best-effort NVIDIA GPU (`nvidia-smi`, `None` on machines
without one — e.g. Apple Silicon), Ollama's currently-loaded model(s) (`GET
/api/ps` — size, VRAM split, `keep_alive` countdown), and rolling per-turn
latency. The latency numbers come from the EventBus's `metric` (voice, one per
pipeline stage) and `chat.turn` (text chat) events, captured by
`system_service.record_turn_metric` — a separate subscriber from
`log_service`, which also listens to these same events but only keeps a
flattened string message, not the numeric fields. `/system` was already taken
(the dashboard restart endpoint), hence `/resources`.

## Python venv

`mcp` is pinned to `1.29.1` — 2.x removed `mcp.server.fastmcp.FastMCP`, which every MCP
server module here uses. (The `integrations/` package is named to avoid shadowing that
`mcp` PyPI import.) `requirements.txt` needs Python 3.10+.

## MCP integration

`integrations/client.py`'s `MCPManager` connects to whatever's listed under `mcp.servers`
in the consuming repo's `config.yaml` — each entry a separate module (own process, own
dependencies), implemented under `integrations/servers/`:

- `claude_code_server.py` (conventionally `projects`, `always_on: true`) — project
  discovery and the Claude Code bridge. Sessions with `SessionMode.CODE` bypass Ollama and
  route to Claude Code directly.
- `devteam_server.py` — background multi-phase Claude Code pipelines; imports
  `find_projects`/`resolve_project` from `claude_code_server.py`.
- `schedule_server.py` — Google Calendar (needs one-time OAuth setup, see
  `docs/schedule-setup.md`).
- `notes_server.py` — local notes/reminders, `~/.dann/notes.json`.
- `gardening_server.py` — garden log (plantings, harvests, care notes).
- `bjj_server.py` — BJJ training log.
- `system_server.py` — volume/open-app/lock-screen via `osascript`.
- `focus_areas_server.py` — persistent per-topic notes recalled across sessions (see
  `shared/focus_areas_config.py`, `shared/focus_areas_store.py`).

Modules default to `always_on: false` — registered but not started. `MCPManager` exposes
three meta-tools (`list_modules`, `enable_module`, `disable_module`) so the LLM starts a
module's process only when a turn actually needs it. `always_on: true` is the escape hatch
for a module that should just always be connected.

`MCPManager` is a process-wide shared instance (`get_shared_manager()`) — both the voice
orchestrator and text chat (`app/services/chat_service.py`) use the same server processes
and tool state rather than starting their own.

Personal per-machine module data (OAuth tokens, notes) lives under `~/.dann/`, not in the
repo — see `integrations/servers/_store.py`. (`~/.dann/` is a legacy name from before the
extraction; not worth renaming just for cosmetics.)

## Known rough edges

- `app/services/devteam_service.py` reads `~/.dann/devteam_jobs.json` written by
  `devteam_server.py` — a loose coupling via a shared file, not an import, so it's fine
  for this to live here even though "devteam" only makes sense for a coding-partner-style
  persona. Not worth splitting out further.
- `models/openwakeword` and `models/piper-sample-generator` are tracked as git submodule
  gitlinks but this repo has no `.gitmodules` entry for them (inherited from
  `dann-of-thursday`'s history as-is) — pre-existing, not something this extraction
  introduced or fixed.
