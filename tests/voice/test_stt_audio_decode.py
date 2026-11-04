"""faster-whisper decodes audio through PyAV. PyAV 19 dropped the
`metadata_errors` argument faster-whisper 1.2 still passes, which broke every
voice turn ("open() got an unexpected keyword argument 'metadata_errors'")."""

import wave

import numpy as np


def test_faster_whisper_can_decode_a_wav(tmp_path):
    from faster_whisper.audio import decode_audio

    path = tmp_path / "tone.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes((np.sin(np.arange(16000) / 10) * 8000).astype(np.int16).tobytes())

    audio = decode_audio(str(path), sampling_rate=16000)
    assert len(audio) == 16000
