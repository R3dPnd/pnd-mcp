"""Delivers the job-hunt morning report (and announcements from hunts that
finished while Akane was down) once, at the first good moment:

- when the voice pipeline is ready (`state.changed` running) — speech has a
  listener by then;
- otherwise at the user's first interaction (`session.start`, `chat.turn`);
- in silent mode (no voice pipeline), at API startup, to the chat only.

Never on its own overnight: a report written at 4am waits for one of these.
"""

from __future__ import annotations

import threading
from datetime import date, datetime
from typing import Any

from app.services import chat_service
from integrations.job_search.delivery import Delivery, due
from shared.persona import data_dir
from voice.event_bus import bus

CHAT_TITLE = "Morning report"
_TRIGGERS = ("session.start", "chat.turn")
_lock = threading.Lock()
_listener = None


def deliver_now(reason: str) -> bool:
    with _lock:
        delivery: Delivery = due(data_dir(), date.today().isoformat(), datetime.now().isoformat(timespec="seconds"))
    for text in delivery.spoken:
        bus.emit("announce", {"text": text})
    for text in delivery.chat:
        chat_service.post_assistant_message(CHAT_TITLE, text)
    return bool(delivery.spoken or delivery.chat)


def _on_event(event_type: str, payload: dict[str, Any]) -> None:
    if event_type in _TRIGGERS or (event_type == "state.changed" and payload.get("running") is True):
        deliver_now(event_type)


def install(voice_pipeline: bool) -> None:
    global _listener
    uninstall()
    _listener = _on_event
    bus.subscribe(_listener)
    if not voice_pipeline:
        deliver_now("startup")


def uninstall() -> None:
    global _listener
    if _listener is not None:
        bus.unsubscribe(_listener)
        _listener = None
