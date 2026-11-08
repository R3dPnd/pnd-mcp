"""Unit tests for the audio capture module."""

import wave
import pytest
import numpy as np
from pathlib import Path
from unittest.mock import patch

from voice.audio.capture import save_wav


# ── save_wav ──────────────────────────────────────────────────────────────────

class TestSaveWav:
    def test_creates_valid_wav_file(self, tmp_path):
        pcm = np.zeros(1600, dtype=np.int16).tobytes()
        out = tmp_path / "test.wav"
        save_wav(pcm, out, sample_rate=16000)

        assert out.exists()
        with wave.open(str(out), "rb") as wf:
            assert wf.getnchannels() == 1
            assert wf.getsampwidth() == 2
            assert wf.getframerate() == 16000

    def test_frame_count_matches_pcm_length(self, tmp_path):
        n_samples = 3200
        pcm = np.zeros(n_samples, dtype=np.int16).tobytes()
        out = tmp_path / "test.wav"
        save_wav(pcm, out, sample_rate=16000)

        with wave.open(str(out), "rb") as wf:
            assert wf.getnframes() == n_samples

    def test_custom_sample_rate_written(self, tmp_path):
        pcm = np.zeros(44100, dtype=np.int16).tobytes()
        out = tmp_path / "test44k.wav"
        save_wav(pcm, out, sample_rate=44100)

        with wave.open(str(out), "rb") as wf:
            assert wf.getframerate() == 44100

    def test_empty_pcm_creates_empty_wav(self, tmp_path):
        out = tmp_path / "empty.wav"
        save_wav(b"", out)

        with wave.open(str(out), "rb") as wf:
            assert wf.getnframes() == 0

    def test_roundtrip_preserves_samples(self, tmp_path):
        """Samples written then read back should be identical."""
        rng = np.random.default_rng(42)
        samples = rng.integers(-32768, 32767, size=800, dtype=np.int16)
        pcm = samples.tobytes()
        out = tmp_path / "roundtrip.wav"
        save_wav(pcm, out)

        with wave.open(str(out), "rb") as wf:
            raw = wf.readframes(wf.getnframes())

        recovered = np.frombuffer(raw, dtype=np.int16)
        np.testing.assert_array_equal(samples, recovered)


# ── RMS energy gate (inline logic mirroring orchestrator._run_turn) ───────────

class TestRmsEnergyGate:
    """Test the RMS calculation used to gate silent audio before STT."""

    _MIN_SPEECH_RMS = 0.005

    def _rms(self, pcm: bytes) -> float:
        arr = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32767
        return float(np.sqrt(np.mean(arr ** 2)))

    def test_silence_below_threshold(self):
        silence = np.zeros(1600, dtype=np.int16).tobytes()
        assert self._rms(silence) < self._MIN_SPEECH_RMS

    def test_loud_audio_above_threshold(self):
        loud = np.full(1600, 10000, dtype=np.int16).tobytes()
        assert self._rms(loud) > self._MIN_SPEECH_RMS

    def test_near_silence_at_boundary(self):
        # Just below the threshold (rms ≈ 0.003)
        quiet = (np.ones(1600, dtype=np.int16) * 100).tobytes()
        rms = self._rms(quiet)
        assert rms < self._MIN_SPEECH_RMS

    def test_speech_level_audio_passes(self):
        # Typical speech at ~30% of full scale
        speech = (np.ones(1600, dtype=np.int16) * 10000).tobytes()
        rms = self._rms(speech)
        assert rms > self._MIN_SPEECH_RMS


# ── Recovering the speaker after sleep / device changes ──────────────────────

class TestPlaybackRecovery:
    """Live: after two days asleep, the long-running process's PortAudio
    state was stale — 'Error opening OutputStream: Internal PortAudio error
    [-9986]' — while a fresh process opened the same speaker fine."""

    def _wav(self, tmp_path):
        import numpy as np
        import soundfile as sf
        path = tmp_path / "x.wav"
        sf.write(str(path), np.zeros(160, dtype="float32"), 16000)
        return path

    def test_a_stale_audio_system_is_refreshed_and_retried(self, tmp_path):
        import sounddevice as sd
        from voice.audio import playback
        calls = []

        def play(*a, **k):
            calls.append("play")
            if len(calls) == 1:
                raise sd.PortAudioError("Error opening OutputStream: Internal PortAudio error", -9986)

        with patch.object(playback.sd, "play", side_effect=play), patch.object(playback.sd, "wait"), \
             patch.object(playback.sd, "_terminate", side_effect=lambda: calls.append("terminate")), \
             patch.object(playback.sd, "_initialize", side_effect=lambda: calls.append("initialize")):
            playback.play_wav(self._wav(tmp_path))
        assert calls == ["play", "terminate", "initialize", "play"]

    def test_a_speaker_that_still_fails_raises(self, tmp_path):
        import pytest
        import sounddevice as sd
        from voice.audio import playback
        err = sd.PortAudioError("nope", -9986)
        with patch.object(playback.sd, "play", side_effect=err), patch.object(playback.sd, "wait"), \
             patch.object(playback.sd, "_terminate"), patch.object(playback.sd, "_initialize"):
            with pytest.raises(sd.PortAudioError):
                playback.play_wav(self._wav(tmp_path))
