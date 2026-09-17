"""Unit tests for app/services/system_service.py — the System panel's data
source (host memory/CPU/GPU, Ollama's loaded model(s), rolling per-turn
latency). memory_status/cpu_status call real psutil and are only sanity-
checked for shape; gpu_status/ollama_status are mocked at their I/O
boundary (subprocess/requests) since this machine has no NVIDIA GPU and
tests shouldn't depend on Ollama actually running.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.services import system_service


@pytest.fixture(autouse=True)
def _clear_turn_history():
    """Each test gets a clean ring buffer — system_service's module-level
    deque is process-global, same pattern as metrics_service's tests."""
    system_service._turn_history.clear()
    yield
    system_service._turn_history.clear()


# ── record_turn_metric / recent_turns / turn_stats ──────────────────────────────

class TestTurnHistory:
    def test_non_turn_events_are_ignored(self):
        system_service.record_turn_metric("state.changed", {"mode": "code"})
        assert system_service.recent_turns() == []

    def test_metric_event_recorded(self):
        system_service.record_turn_metric("metric", {"stt_ms": 100, "llm_ms": 200, "tts_ms": 50})
        turns = system_service.recent_turns()
        assert len(turns) == 1
        assert turns[0]["stt_ms"] == 100
        assert turns[0]["event_type"] == "metric"
        assert "recorded_at" in turns[0]

    def test_chat_turn_event_recorded(self):
        system_service.record_turn_metric("chat.turn", {"latency_ms": 500, "focus_area": "coding"})
        turns = system_service.recent_turns()
        assert len(turns) == 1
        assert turns[0]["latency_ms"] == 500
        assert turns[0]["event_type"] == "chat.turn"

    def test_recent_turns_respects_limit_and_order(self):
        for i in range(5):
            system_service.record_turn_metric("chat.turn", {"latency_ms": i})
        turns = system_service.recent_turns(limit=3)
        assert [t["latency_ms"] for t in turns] == [2, 3, 4]

    def test_ring_buffer_caps_at_max_history(self):
        for i in range(system_service._MAX_TURN_HISTORY + 20):
            system_service.record_turn_metric("chat.turn", {"latency_ms": i})
        assert len(system_service.recent_turns(limit=1000)) == system_service._MAX_TURN_HISTORY

    def test_turn_stats_averages_each_stage_independently(self):
        system_service.record_turn_metric("metric", {"stt_ms": 100, "llm_ms": 300})
        system_service.record_turn_metric("metric", {"stt_ms": 200, "llm_ms": 500})
        system_service.record_turn_metric("chat.turn", {"latency_ms": 1000})

        stats = system_service.turn_stats()

        assert stats["sample_count"] == 3
        assert stats["avg_stt_ms"] == 150.0
        assert stats["avg_llm_ms"] == 400.0
        assert stats["avg_chat_latency_ms"] == 1000.0
        assert stats["avg_tts_ms"] is None  # no samples with this key — None, not 0

    def test_turn_stats_with_no_history_returns_all_none(self):
        stats = system_service.turn_stats()
        assert stats == {
            "sample_count": 0,
            "avg_stt_ms": None,
            "avg_llm_ms": None,
            "avg_tts_ms": None,
            "avg_code_ms": None,
            "avg_chat_latency_ms": None,
        }

    def test_zero_values_excluded_from_average_not_counted_as_data(self):
        """A stage that legitimately took 0ms would be indistinguishable
        from 'no data' under the current filter (falsy 0 is excluded) —
        documenting that as current behavior, not asserting it's ideal."""
        system_service.record_turn_metric("metric", {"stt_ms": 0})
        stats = system_service.turn_stats()
        assert stats["avg_stt_ms"] is None


# ── memory_status / cpu_status ───────────────────────────────────────────────────

class TestHostStatus:
    def test_memory_status_shape(self):
        result = system_service.memory_status()
        assert result["total_bytes"] > 0
        assert 0 <= result["percent"] <= 100
        assert result["used_bytes"] <= result["total_bytes"]

    def test_cpu_status_shape(self):
        result = system_service.cpu_status()
        assert result["core_count"] >= 1
        assert len(result["per_core_percent"]) == result["core_count"]
        assert 0 <= result["percent"] <= 100


# ── gpu_status ────────────────────────────────────────────────────────────────

class TestGpuStatus:
    def test_no_nvidia_smi_returns_none(self):
        with patch("app.services.system_service.shutil.which", return_value=None):
            assert system_service.gpu_status() is None

    def test_parses_nvidia_smi_output(self):
        mock_result = MagicMock(returncode=0, stdout="NVIDIA GeForce RTX 4090, 42, 2048, 24576\n")
        with patch("app.services.system_service.shutil.which", return_value="/usr/bin/nvidia-smi"), \
             patch("app.services.system_service.subprocess.run", return_value=mock_result):
            status = system_service.gpu_status()
        assert status == {"gpus": [{
            "name": "NVIDIA GeForce RTX 4090",
            "utilization_percent": 42.0,
            "memory_used_mb": 2048.0,
            "memory_total_mb": 24576.0,
        }]}

    def test_nonzero_exit_returns_none(self):
        mock_result = MagicMock(returncode=1, stdout="")
        with patch("app.services.system_service.shutil.which", return_value="/usr/bin/nvidia-smi"), \
             patch("app.services.system_service.subprocess.run", return_value=mock_result):
            assert system_service.gpu_status() is None

    def test_subprocess_exception_returns_none_not_raises(self):
        with patch("app.services.system_service.shutil.which", return_value="/usr/bin/nvidia-smi"), \
             patch("app.services.system_service.subprocess.run", side_effect=OSError("boom")):
            assert system_service.gpu_status() is None


# ── ollama_status ─────────────────────────────────────────────────────────────

class TestOllamaStatus:
    def test_returns_parsed_json_on_success(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"models": [{"name": "dann-router", "size": 4683087361}]}
        with patch("app.services.system_service.requests.get", return_value=mock_resp):
            result = system_service.ollama_status("http://localhost:11434")
        assert result == {"models": [{"name": "dann-router", "size": 4683087361}]}

    def test_unreachable_ollama_returns_none_not_raises(self):
        with patch("app.services.system_service.requests.get", side_effect=ConnectionError("refused")):
            assert system_service.ollama_status("http://localhost:11434") is None

    def test_trailing_slash_in_base_url_handled(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"models": []}
        with patch("app.services.system_service.requests.get", return_value=mock_resp) as mock_get:
            system_service.ollama_status("http://localhost:11434/")
        mock_get.assert_called_once_with("http://localhost:11434/api/ps", timeout=system_service._OLLAMA_TIMEOUT_S)


# ── full_status ───────────────────────────────────────────────────────────────

class TestFullStatus:
    def test_aggregates_all_sections(self):
        with patch("app.services.system_service.gpu_status", return_value=None), \
             patch("app.services.system_service.ollama_status", return_value={"models": []}):
            result = system_service.full_status("http://localhost:11434")
        assert set(result.keys()) == {"memory", "cpu", "gpu", "ollama", "turns"}
