# Persona config

pnd-mcp doesn't know who it's running as until the persona repo's
`config.yaml` tells it. Everything that used to be hardcoded to Dann — the
display name, the wake phrase shown in the UI, the data directory, the ports —
comes from the `persona:` block, read by `shared/persona.py`.

## The `persona:` block

```yaml
persona:
  name: Akane              # UI tab + page title, window title, API title, log file name
  wake_phrase: "ok Akane"  # shown in the UI ("Listening for 'ok Akane'")
  data_dir: ~/.akane       # notes, history, logs, OAuth tokens, focus areas
  api_port: 8000
  ui_port: 3000
```

Every key is optional. The defaults are the old hardcoded values, so a config
with no `persona:` block (dann-of-thursday's) behaves exactly as before:

| Key | Default |
|---|---|
| `name` | `Dann` |
| `wake_phrase` | `ok Dann` |
| `data_dir` | `~/.dann` |
| `api_port` | `8000` |
| `ui_port` | `3000` |

`wake_phrase` is display text only. The wake-word *model* is still
`wake_word.model`; train one for a new phrase with
`scripts/wakeword/` (see `wakeword_args.py` for the `--phrases-file` format).

## `config.local.yaml` — per-machine overrides

If a `config.local.yaml` sits next to `config.yaml`, it's merged over it when
the config loads (`voice/config.py`'s `load_config`). Keep it gitignored in the
persona repo and put machine-specific things there: the Ollama model, Whisper
size, audio devices, absolute paths to other repos.

Merge rules: nested mappings merge key by key; lists and scalars replace the
base value outright (a local `agents:` list replaces the whole base list). An
empty file is ignored.

## Environment variables

`PND_*` names win; the old `DANN_*` names are still read as fallbacks.

| Variable | Fallback | Used by | Meaning |
|---|---|---|---|
| `PND_CONFIG_PATH` | `DANN_CONFIG_PATH` | `load_config` | path to the persona's `config.yaml` |
| `PND_DATA_DIR` | — | `shared.persona.data_dir` | overrides `persona.data_dir`; injected into every MCP tool-server's env by `MCPManager` (the stdio client doesn't pass the parent's env through) |
| `PND_API_BASE_URL` | `DANN_API_BASE_URL` | `claude_code_server` | dashboard API the Claude Code tools talk to; default `http://localhost:<persona.api_port>` |
| `PND_API_PORT` / `PND_UI_PORT` | — | `ui/vite.config.ts`, `ui/electron/main.cjs` | ports for the Vite dev server/proxy and Electron's own backend |
| `PND_FULLSCREEN` | `DANN_FULLSCREEN` | Electron | start fullscreen when `1` |
| `PND_PERSONA_NAME` | — | Electron | window title before the page loads |

## Claude usage

All one-shot `claude` CLI calls go through `shared/claude_cli.py`, and every
`claude` launch (including dashboard terminals and devteam pipelines) uses
`claude_env()`, which drops `ANTHROPIC_API_KEY`/`ANTHROPIC_AUTH_TOKEN` so the
CLI runs on the Claude Code subscription. There's no billed-SDK fallback.

`ask_claude` and `web_search` live in `integrations/servers/claude_server.py`,
so a persona can enable research/reasoning without the coding tools.
`claude_code_server` still exposes both names (delegating) for configs that
route to them there.
