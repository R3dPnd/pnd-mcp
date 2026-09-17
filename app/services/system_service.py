"""System + LLM resource status.

Host memory/CPU/GPU, Ollama's currently loaded model(s) (size, VRAM split,
keep_alive countdown), and rolling per-turn latency — for the dashboard's
System panel and the standalone Electron window (see
dann-of-thursday/docs/system-status.md for the feature's origin).

Separate from metrics_service.py, which is specifically shaped around
Claude Code call records (project/status/latency_ms) — this module is
about the host machine and the LLM backend, not any one tool integration.

Turn latency comes from the EventBus's "metric" (voice, one per pipeline
stage) and "chat.turn" (text chat, one per message) events. log_service.py
also subscribes to these, but only keeps a human-readable string per entry
— record_turn_metric keeps the numeric fields (stt_ms/llm_ms/tts_ms/
code_ms/latency_ms) intact for aggregation.
"""

from __future__ import annotations

import shutil
import subprocess
import threading
import time
from collections import deque
from typing import Any

import psutil
import requests

_MAX_TURN_HISTORY = 100
_turn_history: deque[dict[str, Any]] = deque(maxlen=_MAX_TURN_HISTORY)
_lock = threading.Lock()

_GPU_PROBE_TIMEOUT_S = 2
_OLLAMA_TIMEOUT_S = 2


def record_turn_metric(event_type: str, payload: dict[str, Any]) -> None:
    """EventBus subscriber — call bus.subscribe(record_turn_metric) once at
    startup alongside the other subscribers (see app/main.py)."""
    if event_type not in ("metric", "chat.turn"):
        return
    with _lock:
        _turn_history.append({**payload, "event_type": event_type, "recorded_at": time.time()})


def recent_turns(limit: int = 20) -> list[dict[str, Any]]:
    """Most recent turn records, oldest first, for a latency-over-time chart."""
    with _lock:
        items = list(_turn_history)
    return items[-limit:]


def turn_stats() -> dict[str, Any]:
    """Rolling averages over everything currently in the ring buffer, split
    by pipeline stage. None for a stage with no samples yet, not 0 — 0 would
    misleadingly read as "fast" rather than "no data"."""
    with _lock:
        items = list(_turn_history)

    def _avg(key: str) -> float | None:
        values = [i[key] for i in items if isinstance(i.get(key), (int, float)) and i.get(key)]
        return round(sum(values) / len(values), 1) if values else None

    return {
        "sample_count": len(items),
        "avg_stt_ms": _avg("stt_ms"),
        "avg_llm_ms": _avg("llm_ms"),
        "avg_tts_ms": _avg("tts_ms"),
        "avg_code_ms": _avg("code_ms"),
        "avg_chat_latency_ms": _avg("latency_ms"),
    }


def memory_status() -> dict[str, Any]:
    vm = psutil.virtual_memory()
    return {
        "total_bytes": vm.total,
        "used_bytes": vm.used,
        "available_bytes": vm.available,
        "percent": vm.percent,
    }


def cpu_status() -> dict[str, Any]:
    return {
        # interval=0.1 blocks briefly for a real sample rather than
        # returning 0.0 (psutil's documented behavior for interval=None on
        # the very first call in a process) — acceptable for an on-demand
        # status endpoint, not a hot loop.
        "percent": psutil.cpu_percent(interval=0.1),
        "per_core_percent": psutil.cpu_percent(interval=None, percpu=True),
        "core_count": psutil.cpu_count(logical=True),
    }


def gpu_status() -> dict[str, Any] | None:
    """Best-effort NVIDIA GPU stats via nvidia-smi. Returns None (not an
    error) on machines without one — e.g. Apple Silicon, which has no
    equivalent live-utilization tool available without sudo
    (powermetrics) — so the caller can render "not available" rather than
    a broken gauge."""
    if not shutil.which("nvidia-smi"):
        return None
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,utilization.gpu,memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=_GPU_PROBE_TIMEOUT_S,
        )
        if result.returncode != 0:
            return None
        gpus = []
        for line in result.stdout.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) != 4:
                continue
            name, util, mem_used, mem_total = parts
            gpus.append({
                "name": name,
                "utilization_percent": float(util),
                "memory_used_mb": float(mem_used),
                "memory_total_mb": float(mem_total),
            })
        return {"gpus": gpus} if gpus else None
    except Exception:
        return None


def ollama_status(base_url: str) -> dict[str, Any] | None:
    """Currently loaded Ollama model(s) via GET /api/ps — each with its
    resident size, how much sits in VRAM vs. RAM, and when it'll be
    unloaded (keep_alive). None if Ollama isn't reachable, not an error —
    Ollama not running yet is a normal state, not a fault."""
    try:
        resp = requests.get(f"{base_url.rstrip('/')}/api/ps", timeout=_OLLAMA_TIMEOUT_S)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def full_status(ollama_base_url: str) -> dict[str, Any]:
    return {
        "memory": memory_status(),
        "cpu": cpu_status(),
        "gpu": gpu_status(),
        "ollama": ollama_status(ollama_base_url),
        "turns": turn_stats(),
    }
