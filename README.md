# pnd-mcp

Reusable local-first AI agent runtime: voice pipeline (wake word → STT → LLM
routing → TTS), an MCP client + a library of MCP tool-servers, a FastAPI +
React observability dashboard, and the deploy/setup tooling to run it all on
a personal workstation.

This code was extracted from [dann-of-thursday](https://github.com/R3dPnd/dann-of-thursday)
so that repo could hyper-focus on being a specific assistant persona (a
coding partner / Godot game-dev assistant), while the generic runtime lives
here and can be reused by other personas.

## What's here

```
voice/          Voice pipeline: wake word → STT (faster-whisper) → LLM router (Ollama) → TTS (Piper)
integrations/   MCP client (MCPManager) + tool-server library:
                  claude_code_server  — discover/resolve projects, launch Claude Code sessions over MCP
                  devteam_server      — start/check dev pipeline jobs (builds on claude_code_server)
                  notes, schedule, gardening, bjj, system, focus_areas — general-purpose personal-assistant tools
shared/         Cross-cutting code used by voice/ and app/ (agent routing config, restart)
app/            FastAPI backend serving dashboard state, REST, WebSocket
ui/             React + Tailwind dashboard (Vite dev server / optional Electron)
models/         Wake word models, Piper voice, openwakeword + piper-sample-generator submodules
scripts/        Guided setup (scripts/setup.sh), workstation bootstrap, wake-word training tooling
deploy/         Cloudflare Tunnel + launchd templates for remote access
docs/           Tech-spec, UI-spec, wake-word and schedule-integration notes
```

## Using this from a persona repo

A persona repo (like `dann-of-thursday`) is expected to:

1. Depend on this repo (git submodule, or `pip install` once this has a
   package build) rather than vendoring the runtime.
2. Supply its own `config.yaml` — the routing/system prompt that defines
   the persona's identity and which of the tool-servers above are enabled
   for it.
3. Add its own persona-specific MCP tool-servers (e.g. a Godot server) and
   register them alongside the ones here via config, rather than forking
   this repo.

## Setup

See `scripts/setup.sh` for guided setup, or `docs/tech-spec.md` for how the
pieces fit together. `requirements.txt` covers the full stack (voice +
dashboard + MCP tool-servers); trim it if a given persona doesn't need all
of it (e.g. drop `torch`/`onnx` if you're not retraining a wake-word model).

## Status

This is a fresh extraction (see git history — most commits predate the
split and were made inside `dann-of-thursday`). It has not yet been made
installable as a standalone package or dependency; `dann-of-thursday`
still needs to be wired up to consume it. See that repo for current status.
