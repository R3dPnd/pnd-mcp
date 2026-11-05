"""Unit tests for Orchestrator pure-logic methods (no hardware required)."""

import numpy as np
import pytest
from unittest.mock import patch

from voice.orchestrator import Orchestrator, SessionMode


@pytest.fixture()
def orch(minimal_config):
    """Orchestrator instance with config injected, no real hardware initialised."""
    with patch("voice.orchestrator.load_config", return_value=minimal_config):
        o = Orchestrator()
    return o


# ── _is_goodbye ───────────────────────────────────────────────────────────────

class TestIsGoodbye:
    @pytest.mark.parametrize("text", [
        "thanks Dann",
        "thank you dann",
        "thanks Dan",
        "goodbye dann",
        "bye Dann",
        "goodbye Dan.",
        "good bye dann",        # two-word variant
        "Goodbye, Dan.",        # punctuation
        "that's all dann",
        "that is all dan",
        "cheers dann",
        "goodbye",              # standalone ≤4 words
        "cheers",
        "bye bye",
        "that is all",
        "all done",
        "we're done",
    ])
    def test_recognised_as_goodbye(self, orch, text):
        assert orch._is_goodbye(text) is True

    @pytest.mark.parametrize("text", [
        "what is the weather today",
        "could you rephrase that please",
        "open dev diary",
        "code mode for dev diary",
        "bye",           # single word — intentionally excluded (too short to be certain)
        "thanks for explaining that to me",   # >4 words and no name
        "no",
    ])
    def test_not_goodbye(self, orch, text):
        assert orch._is_goodbye(text) is False


# ── _detect_code_entry ────────────────────────────────────────────────────────

class TestDetectCodeEntry:
    @pytest.mark.parametrize("text, expected_project", [
        ("code mode for dev diary", "dev diary"),
        ("enter code mode for fieldwatch api", "fieldwatch api"),
        ("start coding in dann of thursday", "dann of thursday"),
        ("coding mode for dev-diary", "dev-diary"),
        ("enter code mode for agency service", "agency service"),
    ])
    def test_entry_with_project(self, orch, text, expected_project):
        result = orch._detect_code_entry(text)
        assert result == expected_project

    def test_entry_without_project_returns_empty_string(self, orch):
        result = orch._detect_code_entry("enter code mode")
        assert result == ""

    @pytest.mark.parametrize("text", [
        "what is the weather",
        "open dev diary",
        "goodbye",
        "ask claude code to summarise",
    ])
    def test_non_entry_returns_none(self, orch, text):
        assert orch._detect_code_entry(text) is None


# ── _fix_stt ──────────────────────────────────────────────────────────────────

class TestFixStt:
    @pytest.mark.parametrize("raw, expected", [
        ("open cloud code in dev diary", "open claude code in dev diary"),
        ("clod code session",            "claude code session"),
        ("claud code please",            "claude code please"),
        ("no substitution needed",       "no substitution needed"),
        ("CLOUD CODE uppercase",         "claude code uppercase"),
    ])
    def test_substitutions(self, orch, raw, expected):
        assert orch._fix_stt(raw) == expected


# ── _is_json_artifact ────────────────────────────────────────────────────────

class TestIsJsonArtifact:
    @pytest.mark.parametrize("text", [
        '{"name": "open_claude_code", "arguments": {}}',
        '[{"tool": "list_projects"}]',
        '{}',
        '[]',
    ])
    def test_detects_json(self, orch, text):
        assert orch._is_json_artifact(text) is True

    @pytest.mark.parametrize("text", [
        "Claude Code is now open in dev-diary.",
        "The weather is sunny today.",
        "{not valid json",
        "",
        "  ",
    ])
    def test_passes_normal_text(self, orch, text):
        assert orch._is_json_artifact(text) is False


# ── _is_fake_tool_call ────────────────────────────────────────────────────────

class TestIsFakeToolCall:
    @pytest.mark.parametrize("text", [
        'The weather in Tacoma is [web_search(query="weather in Tacoma")].',
        'Let me check that: [ask_claude(question="what is rust")]',
        '[list_projects()]',
    ])
    def test_detects_fake_tool_call(self, orch, text):
        assert orch._is_fake_tool_call(text) is True

    @pytest.mark.parametrize("text", [
        "Claude Code is now open in dev-diary.",
        "The weather is sunny today.",
        "It's 66 degrees in Tacoma right now.",
        "",
    ])
    def test_passes_normal_text(self, orch, text):
        assert orch._is_fake_tool_call(text) is False


# ── _is_rapid_rewake ──────────────────────────────────────────────────────────

class TestIsRapidRewake:
    @pytest.mark.parametrize("since_session_end", [0.0, 0.5, 1.5, 2.9])
    def test_flags_fast_rewake(self, orch, since_session_end):
        assert orch._is_rapid_rewake(since_session_end) is True

    @pytest.mark.parametrize("since_session_end", [3.0, 5.0, 60.0, None])
    def test_passes_normal_gap(self, orch, since_session_end):
        assert orch._is_rapid_rewake(since_session_end) is False


# ── _should_give_up ───────────────────────────────────────────────────────────

class TestShouldGiveUp:
    def test_false_below_threshold(self, orch):
        orch._consecutive_blank_turns = 3
        assert orch._should_give_up() is False

    def test_true_at_threshold(self, orch):
        orch._consecutive_blank_turns = 4
        assert orch._should_give_up() is True


# ── _normalise ────────────────────────────────────────────────────────────────

class TestNormalise:
    def test_strips_punctuation(self, orch):
        assert orch._normalise("Hello, world!") == "hello world"

    def test_collapses_multiple_spaces(self, orch):
        assert orch._normalise("hello,  world") == "hello world"

    def test_collapses_good_bye(self, orch):
        assert orch._normalise("good bye dann") == "goodbye dann"

    def test_lowercases(self, orch):
        assert orch._normalise("THANKS DANN") == "thanks dann"


# ── SessionMode default ───────────────────────────────────────────────────────

def test_session_mode_starts_normal(orch):
    assert orch._mode == SessionMode.NORMAL
    assert orch._code_project is None


# ── Speaking typed-chat replies ───────────────────────────────────────────────

@pytest.fixture()
def speaking_orch(minimal_config):
    """Orchestrator with ux.speak_typed_replies on, a fake detector, and _speak
    recorded instead of synthesizing audio."""
    cfg = {**minimal_config, "ux": {"speak_typed_replies": True}}
    with patch("voice.orchestrator.load_config", return_value=cfg):
        o = Orchestrator()

    class FakeDetector:
        def __init__(self):
            self.calls = []

        def pause(self):
            self.calls.append("pause")

        def resume(self):
            self.calls.append("resume")

    o._detector = FakeDetector()
    o.spoken = []
    o._speak = lambda text: o.spoken.append((text, list(o._detector.calls))) or 0.0
    return o


class TestSpeakTypedReplies:
    def test_typed_reply_is_queued_then_spoken_when_idle(self, speaking_orch):
        speaking_orch._on_bus_event("chat.turn", {"text": "hi", "response": "Hello there."})
        assert speaking_orch.spoken == []  # nothing spoken from the emitting (API) thread
        speaking_orch._speak_queued()
        assert [t for t, _ in speaking_orch.spoken] == ["Hello there."]

    def test_wake_detection_is_paused_while_speaking(self, speaking_orch):
        speaking_orch._on_bus_event("chat.turn", {"response": "Hello there."})
        speaking_orch._speak_queued()
        (_, calls_during_speech), = speaking_orch.spoken
        assert calls_during_speech == ["pause"]
        assert speaking_orch._detector.calls == ["pause", "resume"]

    def test_a_wake_heard_during_its_own_speech_is_discarded(self, speaking_orch):
        speaking_orch._on_bus_event("chat.turn", {"response": "Hello there."})
        speaking_orch._wake_event.set()  # e.g. the mic picked up the TTS
        speaking_orch._speak_queued()
        assert not speaking_orch._wake_event.is_set()

    def test_replies_are_spoken_in_order(self, speaking_orch):
        for reply in ("One.", "Two."):
            speaking_orch._on_bus_event("chat.turn", {"response": reply})
        speaking_orch._speak_queued()
        assert [t for t, _ in speaking_orch.spoken] == ["One.", "Two."]

    def test_empty_replies_and_other_events_are_ignored(self, speaking_orch):
        speaking_orch._on_bus_event("chat.turn", {"response": "   "})
        speaking_orch._on_bus_event("turn.llm", {"response": "voice reply, already spoken"})
        speaking_orch._speak_queued()
        assert speaking_orch.spoken == []

    def test_nothing_queued_means_no_detector_churn(self, speaking_orch):
        speaking_orch._speak_queued()
        assert speaking_orch._detector.calls == []

    def test_off_by_default(self, orch):
        orch._on_bus_event("chat.turn", {"response": "Hello there."})
        assert orch._speech_queue.empty()

    def test_speaking_does_not_unmute_a_user_paused_listener(self, speaking_orch):
        speaking_orch._user_paused = True
        speaking_orch._on_bus_event("chat.turn", {"response": "Hello there."})
        speaking_orch._speak_queued()
        assert speaking_orch._detector.calls == ["pause"]


# ── Silent turns end the session ──────────────────────────────────────────────

class TestSilentTurns:
    """A false wake in a quiet room used to leave the session recording
    forever: silent recordings returned True without counting as blank."""

    @pytest.mark.parametrize("pcm", [b"", np.zeros(16000, dtype=np.int16).tobytes()])
    def test_repeated_silence_ends_the_session(self, orch, pcm):
        from voice.orchestrator import _MAX_CONSECUTIVE_BLANK_TURNS

        orch._record = lambda: pcm
        orch._speak = lambda text: 0.0
        results = [orch._run_turn() for _ in range(_MAX_CONSECUTIVE_BLANK_TURNS)]
        assert results[:-1] == [True] * (_MAX_CONSECUTIVE_BLANK_TURNS - 1)
        assert results[-1] is False

    def test_silence_ends_the_session_without_speaking(self, orch):
        from voice.orchestrator import _MAX_CONSECUTIVE_BLANK_TURNS

        spoken = []
        orch._record = lambda: b""
        orch._speak = lambda text: spoken.append(text) or 0.0
        for _ in range(_MAX_CONSECUTIVE_BLANK_TURNS):
            orch._run_turn()
        assert spoken == []
        assert orch._end_reason == "silence"


# ── Speak-only mode (no mic) ──────────────────────────────────────────────────

class TestSpeakOnlyMode:
    """listen=False: typed replies are read aloud, but no wake-word detector is
    created, no STT model is loaded, and the mic is never opened."""

    @pytest.fixture()
    def speak_only(self, minimal_config):
        cfg = {**minimal_config, "ux": {"speak_typed_replies": True}}
        with patch("voice.orchestrator.load_config", return_value=cfg):
            o = Orchestrator(listen=False)
        o.spoken = []
        o._speak = lambda text: o.spoken.append(text) or 0.0
        return o

    def test_run_speaks_typed_replies_without_a_detector_or_stt(self, speak_only):
        def drain_then_stop():
            Orchestrator._speak_queued(speak_only)
            speak_only._running = False

        speak_only._speak_queued = drain_then_stop
        speak_only._on_bus_event("chat.turn", {"response": "Hello there."})
        with patch("voice.orchestrator.warmup_stt") as stt, \
             patch("voice.orchestrator.warmup_tts"), \
             patch("voice.orchestrator.WakeWordDetector") as porcupine:
            speak_only.run()
        assert speak_only._detector is None
        stt.assert_not_called()
        porcupine.assert_not_called()
        assert "Hello there." in speak_only.spoken

    def test_speak_only_reports_not_listening(self, speak_only):
        assert speak_only.snapshot()["listening"] is False

    def test_enable_listening_cannot_open_the_mic(self, speak_only):
        speak_only.enable_listening()
        assert speak_only._detector is None
        assert speak_only.snapshot()["listening"] is False

    def test_listening_is_the_default(self, orch):
        assert orch.snapshot()["listening"] is True


# ── Persona name in spoken commands ───────────────────────────────────────────

class TestPersonaNamedPhrases:
    @pytest.fixture()
    def akane(self, minimal_config):
        cfg = {**minimal_config, "persona": {"name": "Akane"}}
        with patch("voice.orchestrator.load_config", return_value=cfg):
            return Orchestrator()

    @pytest.mark.parametrize("text", ["thanks Akane", "thank you, Akane.", "bye akane", "that's all Akane", "cheers Akane"])
    def test_goodbye_uses_the_persona_name(self, akane, text):
        assert akane._is_goodbye(text) is True

    def test_another_personas_name_is_not_a_goodbye_for_long_utterances(self, akane):
        assert akane._is_goodbye("thanks Dann for explaining all of that") is False

    @pytest.mark.parametrize("text", ["restart Akane", "please restart yourself"])
    def test_restart_uses_the_persona_name(self, akane, text):
        assert akane._is_restart(text) is True

    def test_restart_does_not_answer_to_dann(self, akane):
        assert akane._is_restart("restart Dann") is False

    def test_dann_still_answers_to_dan(self, orch):
        assert orch._is_restart("restart Dann") is True
        assert orch._is_goodbye("thanks dan") is True


class TestPersonaNamedOutput:
    @pytest.fixture()
    def akane(self, minimal_config):
        cfg = {**minimal_config, "persona": {"name": "Akane", "wake_phrase": "ok Akane"}}
        with patch("voice.orchestrator.load_config", return_value=cfg):
            return Orchestrator()

    def test_console_lines_are_prefixed_with_the_persona(self, akane, capsys):
        akane._log("Thinking...")
        assert capsys.readouterr().out == "[akane] Thinking...\n"

    def test_dann_keeps_its_prefix(self, orch, capsys):
        orch._log("Thinking...")
        assert capsys.readouterr().out == "[dann] Thinking...\n"

    def test_listening_line_uses_the_wake_phrase_not_the_model_file(self, akane):
        assert akane._wake_phrase == "ok Akane"


def test_announce_is_spoken_even_with_typed_replies_off(minimal_config):
    with patch("voice.orchestrator.load_config", return_value={**minimal_config, "ux": {}}):
        o = Orchestrator()
    spoken = []
    o._speak = lambda text: spoken.append(text) or 0.0
    o._on_bus_event("announce", {"text": "Morning."})
    o._on_bus_event("chat.turn", {"response": "typed reply"})  # still off
    o._speak_queued()
    assert spoken == ["Morning."]


def test_announcements_made_when_ready_are_heard(minimal_config):
    # Delivery reacts to the orchestrator's "ready" state.changed by emitting
    # announce — the orchestrator must already be subscribed by then.
    from voice.event_bus import bus

    cfg = {**minimal_config, "ux": {"speak_typed_replies": True}}
    with patch("voice.orchestrator.load_config", return_value=cfg):
        o = Orchestrator(listen=False)
    spoken = []
    o._speak = lambda text: spoken.append(text) or 0.0

    def on_ready(t, p):
        if t == "state.changed" and p.get("running"):
            bus.emit("announce", {"text": "Morning."})

    def drain_then_stop():
        Orchestrator._speak_queued(o)
        o._running = False

    o._speak_queued = drain_then_stop
    bus.subscribe(on_ready)
    try:
        with patch("voice.orchestrator.warmup_tts"):
            o.run()
    finally:
        bus.unsubscribe(on_ready)
    assert "Morning." in spoken


class TestSpeechText:
    """What's spoken from typed replies and announcements: links stay on
    screen, not read aloud (live: 'The link is [here](https://annotation…)')."""

    @pytest.fixture()
    def o(self, minimal_config):
        with patch("voice.orchestrator.load_config", return_value={**minimal_config, "ux": {"speak_typed_replies": True}}):
            o = Orchestrator()
        o.spoken = []
        o._speak = lambda text: o.spoken.append(text) or 0.0
        return o

    @pytest.mark.parametrize("reply, spoken", [
        ("The link is [here](https://annotation.academy/jobs/x).", "The link is here."),
        ("See https://jobs.example/a?b=1 for details.", "See for details."),
        ("Done! 😊", "Done!"),
        ("**Number 2** is `remote`.", "Number 2 is remote."),
    ])
    def test_typed_replies_are_spoken_without_links_or_markup(self, o, reply, spoken):
        o._on_bus_event("chat.turn", {"response": reply})
        o._speak_queued()
        assert o.spoken == [spoken]

    def test_nothing_left_to_say_is_not_spoken(self, o):
        o._on_bus_event("chat.turn", {"response": "https://only.example/link"})
        o._speak_queued()
        assert o.spoken == []
