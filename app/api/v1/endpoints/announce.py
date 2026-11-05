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
    chat_text: str | None = None  # posted instead of `text` (e.g. the full lead list)
    stream_id: str | None = None  # post into this stream (falls back to chat_title if it's gone)


@router.post("", summary="Say something when idle, and optionally post it to a chat stream")
async def announce(body: Announcement) -> JSONResponse:
    text = body.text.strip()
    if not text:
        return JSONResponse({"error": "text is required"}, status_code=400)
    bus.emit("announce", {"text": text})
    chat = (body.chat_text or "").strip() or text
    stream_id = None
    if body.stream_id and chat_service.post_to_stream(body.stream_id, chat):
        stream_id = body.stream_id
    elif body.chat_title:
        stream_id = chat_service.post_assistant_message(body.chat_title, chat)
    return JSONResponse({"ok": True, "stream_id": stream_id})
