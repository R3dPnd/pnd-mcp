"""GET /api/v1/persona — who this runtime is running as (config.yaml's
`persona:` block, see shared/persona.py), so the dashboard can show the
persona's own name and wake phrase instead of hardcoding one."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from shared.persona import get_persona

router = APIRouter()


@router.get("", summary="Persona name and wake phrase")
async def get_persona_info() -> JSONResponse:
    persona = get_persona()
    return JSONResponse({"name": persona.name, "wake_phrase": persona.wake_phrase})
