"""POST /api/v1/announce — background work (a finished job hunt, the morning
report) telling the user something: spoken when the voice pipeline is idle,
and optionally posted into a named chat stream."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.services import chat_service
from voice.event_bus import bus

router = APIRouter()


class Announcement(BaseModel):
    text: str
    chat_title: str | None = None


@router.post("", summary="Say something when idle, and optionally post it to a chat stream")
async def announce(body: Announcement) -> JSONResponse:
    text = body.text.strip()
    if not text:
        return JSONResponse({"error": "text is required"}, status_code=400)
    bus.emit("announce", {"text": text})
    stream_id = chat_service.post_assistant_message(body.chat_title, text) if body.chat_title else None
    return JSONResponse({"ok": True, "stream_id": stream_id})
