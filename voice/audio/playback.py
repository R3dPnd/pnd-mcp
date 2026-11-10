"""Play WAV audio through the output device."""

import ctypes
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import sounddevice as sd
import soundfile as sf

_afplay_lock = threading.Lock()
_afplay: subprocess.Popen | None = None


def _fourcc(code: str) -> int:
    return int.from_bytes(code.encode(), "big")


class _PropertyAddress(ctypes.Structure):
    _fields_ = [("selector", ctypes.c_uint32), ("scope", ctypes.c_uint32), ("element", ctypes.c_uint32)]


def _macos_default_output_name() -> str | None:
    """The output macOS has selected right now, asked of CoreAudio directly
    (PortAudio only learns the default once per process). None if unknown."""
    try:
        ca = ctypes.CDLL("/System/Library/Frameworks/CoreAudio.framework/CoreAudio")
        cf = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
        get = ca.AudioObjectGetPropertyData
        get.argtypes = [ctypes.c_uint32, ctypes.POINTER(_PropertyAddress), ctypes.c_uint32,
                        ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32), ctypes.c_void_p]
        get.restype = ctypes.c_int32
        cf.CFStringGetCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_long, ctypes.c_uint32]
        cf.CFStringGetCString.restype = ctypes.c_bool
        cf.CFRelease.argtypes = [ctypes.c_void_p]

        glob = _fourcc("glob")
        device = ctypes.c_uint32()
        size = ctypes.c_uint32(ctypes.sizeof(device))
        addr = _PropertyAddress(_fourcc("dOut"), glob, 0)
        if get(1, ctypes.byref(addr), 0, None, ctypes.byref(size), ctypes.byref(device)) or not device.value:
            return None

        name_ref = ctypes.c_void_p()
        size = ctypes.c_uint32(ctypes.sizeof(name_ref))
        addr = _PropertyAddress(_fourcc("lnam"), glob, 0)
        if get(device.value, ctypes.byref(addr), 0, None, ctypes.byref(size), ctypes.byref(name_ref)) \
                or not name_ref.value:
            return None
        try:
            buf = ctypes.create_string_buffer(512)
            if not cf.CFStringGetCString(name_ref, buf, len(buf), 0x08000100):  # UTF-8
                return None
            return buf.value.decode()
        finally:
            cf.CFRelease(name_ref)
    except (OSError, AttributeError):
        return None


def _system_output_device() -> int | str | None:
    """With no device configured on macOS, play on the output macOS has
    selected now. Live: a process three days old read a reply aloud on the
    laptop speakers after the headset became the default — PortAudio's default
    was the one at startup — and the volume keys couldn't turn it down.

    Returns PortAudio's index for that device when it knows it, "afplay" when
    the device appeared after startup (PortAudio's list is stale, and it can't
    be refreshed while the wake-word mic stream is open), and None to keep
    PortAudio's default (not macOS, or CoreAudio couldn't say)."""
    if sys.platform != "darwin":
        return None
    name = _macos_default_output_name()
    if name is None:
        return None
    for i, dev in enumerate(sd.query_devices()):
        if dev["name"] == name and dev["max_output_channels"] > 0:
            return i
    return "afplay" if shutil.which("afplay") else None


def _play_afplay(path: Path | str) -> None:
    global _afplay
    with _afplay_lock:
        _afplay = subprocess.Popen(["afplay", str(path)],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc = _afplay
    try:
        proc.wait()
    finally:
        with _afplay_lock:
            if _afplay is proc:
                _afplay = None


def play_wav(path: Path | str, device: int | str | None = None) -> None:
    """Play a WAV file and block until finished."""
    follow_system = device is None
    target = _system_output_device() if follow_system else device
    if target == "afplay":
        _play_afplay(path)
        return
    data, samplerate = sf.read(str(path), dtype="float32")
    try:
        sd.play(data, samplerate, device=target)
    except sd.PortAudioError:
        # PortAudio learns the audio devices once per process; after a long
        # sleep or a device change that state goes stale and opening the
        # speaker fails (-9986) though a fresh process works. Refresh, retry once
        # (looking the system output up again: the refresh can renumber devices).
        sd._terminate()
        sd._initialize()
        if follow_system:
            target = _system_output_device()
            if target == "afplay":
                _play_afplay(path)
                return
        sd.play(data, samplerate, device=target)
    sd.wait()


def stop_playback() -> None:
    """Cut off whatever play_wav is playing (it returns)."""
    with _afplay_lock:
        proc = _afplay
    if proc is not None and proc.poll() is None:
        proc.terminate()
    sd.stop()
