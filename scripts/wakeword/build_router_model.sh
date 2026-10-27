#!/usr/bin/env bash
# Builds (or rebuilds) a persona's custom routing model in Ollama.
# Run this after editing the Modelfile, or any time you pull a newer base model.
#
# Usage: build_router_model.sh [name] [modelfile]
#   name       Ollama model name to create (default: dann-router)
#   modelfile  path to the Modelfile, relative to the repo root or absolute
#              (default: models/dann-router.Modelfile)
set -euo pipefail
name="${1:-dann-router}"
modelfile="${2:-models/dann-router.Modelfile}"
# Resolve a relative Modelfile against the caller's cwd before moving to the
# runtime root, so a persona repo can pass its own path.
if [ -f "$modelfile" ]; then modelfile="$(cd "$(dirname "$modelfile")" && pwd)/$(basename "$modelfile")"; fi
cd "$(dirname "$0")/../.."

ollama create "$name" -f "$modelfile"
echo "Built '$name'. Set ollama.model: $name in config.yaml to use it."
