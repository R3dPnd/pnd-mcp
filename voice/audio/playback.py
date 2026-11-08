"""Play WAV audio through default output device."""

from pathlib import Path

import sounddevice as sd
import soundfile as sf


def play_wav(path: Path | str, device: int | None = None) -> None:
    """Play a WAV file and block until finished."""
    data, samplerate = sf.read(str(path), dtype="float32")
    try:
        sd.play(data, samplerate, device=device)
    except sd.PortAudioError:
        # PortAudio learns the audio devices once per process; after a long
        # sleep or a device change that state goes stale and opening the
        # speaker fails (-9986) though a fresh process works. Refresh, retry once.
        sd._terminate()
        sd._initialize()
        sd.play(data, samplerate, device=device)
    sd.wait()


def stop_playback() -> None:
    """Cut off whatever play_wav is playing (its sd.wait() returns)."""
    sd.stop()
