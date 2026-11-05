"""Voice control endpoints — trigger, enable, and disable listening."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from voice.event_bus import bus

router = APIRouter()


@router.post("/trigger", summary="Trigger a voice session")
async def trigger_voice() -> JSONResponse:
    """Simulate a wake word detection to start a full multi-turn voice session."""
    from app.main import orchestrator
    if orchestrator is None or not orchestrator._running:
        raise HTTPException(
            status_code=503,
            detail="Orchestrator not running. Start the server without NO_VOICE=1.",
        )
    orchestrator._on_wake()
    return JSONResponse({"triggered": True})


@router.post("/enable", summary="Enable wake word listening")
async def enable_voice() -> JSONResponse:
    from app.main import orchestrator
    if orchestrator is None or not orchestrator._running:
        raise HTTPException(status_code=503, detail="Orchestrator not running.")
    orchestrator.enable_listening()
    return JSONResponse({"listening": True})


@router.post("/disable", summary="Disable wake word listening")
async def disable_voice() -> JSONResponse:
    from app.main import orchestrator
    if orchestrator is None or not orchestrator._running:
        raise HTTPException(status_code=503, detail="Orchestrator not running.")
    orchestrator.disable_listening()
    return JSONResponse({"listening": False})


class SpeakRequest(BaseModel):
    text: str


def _running_orchestrator():
    from app.main import orchestrator
    if orchestrator is None or not orchestrator._running:
        raise HTTPException(status_code=503, detail="Voice is off, so there's nothing to read aloud with.")
    return orchestrator


@router.post("/speak", summary="Read text aloud (the chat's speaker button)")
async def speak(body: SpeakRequest) -> JSONResponse:
    _running_orchestrator()
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")
    bus.emit("speak", {"text": text})  # spoken when idle, paragraph by paragraph
    return JSONResponse({"queued": True})


@router.post("/speak/stop", summary="Stop reading aloud")
async def stop_speaking() -> JSONResponse:
    _running_orchestrator().stop_speaking()
    return JSONResponse({"stopped": True})
