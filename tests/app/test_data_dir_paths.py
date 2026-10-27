"""Every persisted file must follow the persona data dir at call time — not a
~/.dann path frozen at import — so a persona with `persona.data_dir` set (or
an MCP subprocess given PND_DATA_DIR) never reads or writes Dann's data."""

import importlib

import pytest


@pytest.mark.parametrize("module, fn, filename", [
    ("app.services.chat_service", "_streams_file", "work_streams.json"),
    ("app.services.history_service", "_history_file", "history.jsonl"),
    ("app.services.metrics_service", "_calls_file", "code_calls.jsonl"),
])
def test_service_paths_follow_data_dir(tmp_data_dir, module, fn, filename):
    assert getattr(importlib.import_module(module), fn)() == tmp_data_dir / filename


def test_log_file_follows_data_dir_and_keeps_dann_name_by_default(tmp_data_dir, monkeypatch):
    from app.services import log_service
    from shared import persona
    monkeypatch.setattr(persona, "get_persona", lambda: persona.Persona())
    assert log_service._log_file() == tmp_data_dir / "dann.log"


def test_log_file_named_after_persona(tmp_data_dir, monkeypatch):
    from app.services import log_service
    from shared import persona
    monkeypatch.setattr(persona, "get_persona", lambda: persona.Persona(name="Akane"))
    assert log_service._log_file() == tmp_data_dir / "akane.log"


def test_focus_area_dir_follows_data_dir(tmp_data_dir, monkeypatch):
    from shared import focus_areas_store
    monkeypatch.setattr(focus_areas_store, "_mark_trusted", lambda d: None)  # don't touch ~/.claude.json
    assert focus_areas_store.focus_area_dir("coding") == tmp_data_dir / "focus_areas" / "coding"


def test_schedule_files_follow_data_dir(tmp_data_dir):
    pytest.importorskip("googleapiclient")
    from integrations.servers import schedule_server
    assert schedule_server._credentials_file() == tmp_data_dir / "google_credentials.json"
    assert schedule_server._token_file() == tmp_data_dir / "google_token.json"
