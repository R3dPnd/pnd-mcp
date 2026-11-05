"""One hunt at a time: the nightly run and an on-demand "find me jobs" would
otherwise race on leads.json."""

from __future__ import annotations

import fcntl
from pathlib import Path
from typing import IO


def lock_path(base: Path) -> Path:
    return base / "applications" / "hunt.lock"


def try_lock(path: Path) -> IO | None:
    """An open, exclusively locked file (keep it open while hunting), or None
    if another hunt holds the lock."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(path, "w")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        return None
    return handle


def announce_request_path(base: Path) -> Path:
    """Dropped by "find me jobs" while a hunt is already running (maybe the
    nightly one, which doesn't announce): the running hunt announces when it
    finishes and removes it."""
    return base / "applications" / "announce.request"
