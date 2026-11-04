"""PND_VOICE_MODE=speak starts the voice pipeline without the mic."""

from app import main


def test_default_mode_listens(monkeypatch):
    monkeypatch.delenv("PND_VOICE_MODE", raising=False)
    assert main.voice_listens() is True


def test_speak_mode_does_not_listen(monkeypatch):
    monkeypatch.setenv("PND_VOICE_MODE", "speak")
    assert main.voice_listens() is False


def test_orchestrator_is_built_with_the_mode(monkeypatch):
    built = {}

    class FakeOrchestrator:
        def __init__(self, listen=True):
            built["listen"] = listen

        def run(self):
            pass

    monkeypatch.setenv("PND_VOICE_MODE", "speak")
    monkeypatch.setattr("voice.orchestrator.Orchestrator", FakeOrchestrator)
    main._start_orchestrator()
    assert built == {"listen": False}
