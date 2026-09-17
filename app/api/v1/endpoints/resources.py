"""
Host + LLM resource status — memory/CPU/GPU, Ollama's loaded model(s), and
rolling per-turn latency. See app/services/system_service.py.

GET /api/v1/resources/status        — full snapshot
GET /api/v1/resources/turns?limit=N — recent per-turn latency records
"""
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from voice.config import load_config
from app.services import system_service

router = APIRouter()


def _ollama_base_url() -> str:
    cfg = load_config()
    return (cfg.get("ollama") or {}).get("base_url", "http://localhost:11434")


@router.get("/status", summary="Memory/CPU/GPU, Ollama model state, and turn-latency averages")
async def get_status() -> JSONResponse:
    return JSONResponse(system_service.full_status(_ollama_base_url()))


@router.get("/turns", summary="Recent per-turn latency records (for a chart)")
async def get_turns(limit: int = Query(20, ge=1, le=100)) -> JSONResponse:
    return JSONResponse({"turns": system_service.recent_turns(limit=limit)})
