"""Shared fixtures for the dann-of-thursday test suite."""

import pytest


@pytest.fixture()
def tmp_data_dir(tmp_path, monkeypatch):
    """Point the persona data dir (shared.persona.data_dir, default ~/.dann) at
    a scratch dir so tests never touch the real one."""
    monkeypatch.setenv("PND_DATA_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture()
def tmp_dann_home(tmp_data_dir):
    """Pre-persona name for tmp_data_dir, kept so existing tests read as before."""
    return tmp_data_dir


@pytest.fixture()
def minimal_config():
    """Minimal config dict that satisfies Orchestrator without touching real hardware."""
    return {
        "audio": {
            "sample_rate": 16000,
            "channels": 1,
            "silence_timeout_ms": 1500,
            "max_record_ms": 15000,
            "silence_threshold": 0.01,
            "input_device": None,
            "output_device": None,
        },
        "wake_word": {
            "engine": "porcupine",
            "access_key": "test-key",
            "model_path": "models/ok_dann.ppn",
            "sensitivity": 0.5,
            "debounce": 2,
            "cooldown_ms": 2000,
        },
        "stt": {"model_size": "base", "language": "en", "device": "cpu", "compute_type": "int8"},
        "ollama": {
            "base_url": "http://localhost:11434",
            "model": "llama3.2",
            "system_prompt": "You are a test assistant.",
            "temperature": 0.7,
            "max_tokens": 80,
        },
        "tts": {"voice_model": "models/piper/en_US-lessac-medium", "speed": 1.0},
        "ux": {},
        "mcp": {"servers": []},
    }
