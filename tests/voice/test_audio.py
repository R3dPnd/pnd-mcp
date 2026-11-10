"""Unit tests for the audio capture module."""

import sys
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
            playback.play_wav(self._wav(tmp_path), device=2)
        assert calls == ["play", "terminate", "initialize", "play"]

    def test_a_speaker_that_still_fails_raises(self, tmp_path):
        import pytest
        import sounddevice as sd
        from voice.audio import playback
        err = sd.PortAudioError("nope", -9986)
        with patch.object(playback.sd, "play", side_effect=err), patch.object(playback.sd, "wait"), \
             patch.object(playback.sd, "_terminate"), patch.object(playback.sd, "_initialize"):
            with pytest.raises(sd.PortAudioError):
                playback.play_wav(self._wav(tmp_path), device=2)


# ── Following the output macOS has selected now ───────────────────────────────

class TestPlaybackFollowsSystemOutput:
    """Live: Akane, three days running, read a reply aloud on the laptop
    speakers though the headset was the macOS default — PortAudio had learned
    the default at startup — and the volume keys couldn't turn it down."""

    DEVICES = [
        {"name": "AB13X USB Audio", "max_output_channels": 2},
        {"name": "MacBook Pro Microphone", "max_output_channels": 0},
        {"name": "MacBook Pro Speakers", "max_output_channels": 2},
    ]

    def _wav(self, tmp_path):
        import soundfile as sf
        path = tmp_path / "x.wav"
        sf.write(str(path), np.zeros(160, dtype="float32"), 16000)
        return path

    def _play(self, tmp_path, system_output, device=None, platform="darwin"):
        """Play with macOS reporting `system_output` as its default; returns
        (sd.play mock, Popen mock)."""
        from voice.audio import playback
        with patch.object(playback.sys, "platform", platform), \
             patch.object(playback, "_macos_default_output_name", return_value=system_output), \
             patch.object(playback.sd, "query_devices", return_value=self.DEVICES), \
             patch.object(playback.shutil, "which", return_value="/usr/bin/afplay"), \
             patch.object(playback.subprocess, "Popen") as popen, \
             patch.object(playback.sd, "play") as sd_play, patch.object(playback.sd, "wait"):
            playback.play_wav(self._wav(tmp_path), device=device)
        return sd_play, popen

    def test_plays_on_the_current_macos_output_not_portaudios_startup_default(self, tmp_path):
        sd_play, popen = self._play(tmp_path, "AB13X USB Audio")
        assert sd_play.call_args.kwargs["device"] == 0
        popen.assert_not_called()

    def test_follows_a_switch_back_to_the_speakers(self, tmp_path):
        sd_play, _ = self._play(tmp_path, "MacBook Pro Speakers")
        assert sd_play.call_args.kwargs["device"] == 2

    def test_a_device_newer_than_portaudios_list_plays_through_afplay(self, tmp_path):
        sd_play, popen = self._play(tmp_path, "AirPods Pro")
        sd_play.assert_not_called()
        assert popen.call_args.args[0][0] == "afplay"
        popen.return_value.wait.assert_called_once()

    def test_a_configured_device_is_used_as_is(self, tmp_path):
        sd_play, popen = self._play(tmp_path, "AB13X USB Audio", device="MacBook Pro Speakers")
        assert sd_play.call_args.kwargs["device"] == "MacBook Pro Speakers"
        popen.assert_not_called()

    def test_coreaudio_unknown_keeps_portaudios_default(self, tmp_path):
        sd_play, popen = self._play(tmp_path, None)
        assert sd_play.call_args.kwargs["device"] is None
        popen.assert_not_called()

    def test_off_macos_keeps_portaudios_default(self, tmp_path):
        sd_play, popen = self._play(tmp_path, "AB13X USB Audio", platform="linux")
        assert sd_play.call_args.kwargs["device"] is None
        popen.assert_not_called()

    def test_the_refresh_retry_looks_the_output_up_again(self, tmp_path):
        """A PortAudio refresh can renumber devices, so the retry re-resolves."""
        import sounddevice as sd
        from voice.audio import playback
        lists = [self.DEVICES, list(reversed(self.DEVICES))]
        played = []

        def play(data, sr, device=None):
            played.append(device)
            if len(played) == 1:
                raise sd.PortAudioError("Internal PortAudio error", -9986)

        with patch.object(playback.sys, "platform", "darwin"), \
             patch.object(playback, "_macos_default_output_name", return_value="AB13X USB Audio"), \
             patch.object(playback.sd, "query_devices", side_effect=lambda: lists.pop(0)), \
             patch.object(playback.sd, "play", side_effect=play), patch.object(playback.sd, "wait"), \
             patch.object(playback.sd, "_terminate"), patch.object(playback.sd, "_initialize"):
            playback.play_wav(self._wav(tmp_path))
        assert played == [0, 2]

    def test_stop_cuts_off_afplay(self, tmp_path):
        import threading
        from voice.audio import playback
        started, done = threading.Event(), threading.Event()

        class FakeProc:
            def __init__(self, *a, **k):
                self.killed = threading.Event()
            def wait(self):
                started.set()
                self.killed.wait(5)
            def poll(self):
                return 0 if self.killed.is_set() else None
            def terminate(self):
                self.killed.set()

        with patch.object(playback.sys, "platform", "darwin"), \
             patch.object(playback, "_macos_default_output_name", return_value="AirPods Pro"), \
             patch.object(playback.sd, "query_devices", return_value=self.DEVICES), \
             patch.object(playback.shutil, "which", return_value="/usr/bin/afplay"), \
             patch.object(playback.subprocess, "Popen", FakeProc), patch.object(playback.sd, "stop"):
            t = threading.Thread(target=lambda: (playback.play_wav(self._wav(tmp_path)), done.set()))
            t.start()
            assert started.wait(5)
            playback.stop_playback()
            assert done.wait(5)
            t.join()
        assert playback._afplay is None

    def test_stop_with_nothing_playing_is_harmless(self):
        from voice.audio import playback
        with patch.object(playback.sd, "stop") as sd_stop:
            playback.stop_playback()
        sd_stop.assert_called_once()

    @pytest.mark.skipif(sys.platform != "darwin", reason="CoreAudio is macOS-only")
    def test_coreaudio_names_a_real_output_device(self):
        import sounddevice as sd
        from voice.audio import playback
        name = playback._macos_default_output_name()
        if name is None:
            pytest.skip("no output device (headless)")
        assert any(d["name"] == name for d in sd.query_devices())
