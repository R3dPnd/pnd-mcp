"""A chat waiting on background work (think_deeply, a job hunt) says so —
the dashboard shows a working indicator until the result is posted."""

import time

from app.services import chat_service
from tests.app.test_announce import chat  # noqa: F401  (fixture)
from voice.event_bus import bus


def _send_with_tool(chat, stream_id, tool, monkeypatch):
    monkeypatch.setattr(chat_service, "get_shared_manager", lambda: type("M", (), {"tools": []})())

    def generate(text, on_tool=None, **kw):
        on_tool(tool)
        return "On it."

    monkeypatch.setattr(chat_service, "generate_response", generate)
    chat_service.send_message(stream_id, "do the thing")


def test_think_deeply_marks_the_chat_as_waiting_until_the_answer_arrives(chat, monkeypatch):
    stream = chat_service.create_stream("general", "plans")
    events = []
    listener = lambda t, p: events.append(t)
    bus.subscribe(listener)
    try:
        _send_with_tool(chat, stream["id"], "think_deeply", monkeypatch)
    finally:
        bus.unsubscribe(listener)
    pending = chat_service.get_stream(stream["id"])["pending_job"]
    assert pending["label"] == "Claude is working on it" and pending["started"] <= time.time()
    assert "chat.job" in events
    chat_service.post_to_stream(stream["id"], "## The plan")
    assert chat_service.get_stream(stream["id"]).get("pending_job") is None


def test_a_job_hunt_clears_when_the_hunt_posts_its_results(chat, monkeypatch):
    stream = chat_service.create_stream("general", "jobs")
    _send_with_tool(chat, stream["id"], "start_hunt", monkeypatch)
    assert chat_service.get_stream(stream["id"])["pending_job"]["label"] == "Job hunt running"
    chat_service.post_assistant_message("Morning report", "## 9. …")
    assert chat_service.get_stream(stream["id"]).get("pending_job") is None


def test_ordinary_tools_dont_mark_the_chat(chat, monkeypatch):
    stream = chat_service.create_stream("general", "q")
    _send_with_tool(chat, stream["id"], "web_search", monkeypatch)
    assert chat_service.get_stream(stream["id"]).get("pending_job") is None


def test_a_stale_marker_expires(chat, monkeypatch):
    # A crashed background process never posts; don't spin forever.
    stream = chat_service.create_stream("general", "q")
    _send_with_tool(chat, stream["id"], "think_deeply", monkeypatch)
    chat_service.get_stream(stream["id"])["pending_job"]["started"] = time.time() - 21 * 60
    assert chat_service.get_stream(stream["id"]).get("pending_job") is None
    assert all(s.get("pending_job") is None for s in chat_service.list_streams())


def _model_view_of_next_turn(stream_id, monkeypatch):
    monkeypatch.setattr(chat_service, "get_shared_manager", lambda: type("M", (), {"tools": []})())
    seen = {}

    def generate(text, system_prompt="", history=(), **kw):
        seen.update(prompt=system_prompt, history=list(history), text=text)
        return "ok"

    monkeypatch.setattr(chat_service, "generate_response", generate)
    chat_service.send_message(stream_id, "are you working on it?")
    return seen


def test_the_model_is_told_nothing_is_running(chat, monkeypatch):
    # Live: "Are you working on it?" → "I'm still working on it" with nothing running.
    stream = chat_service.create_stream("general", "q")
    seen = _model_view_of_next_turn(stream["id"], monkeypatch)
    assert "Nothing is running in the background for this chat" in seen["text"]
    assert seen["text"].endswith("are you working on it?")
    # Only what the user typed is kept in the chat.
    assert chat_service.get_stream(stream["id"])["messages"][-2]["content"] == "are you working on it?"


def test_the_model_is_told_what_is_running(chat, monkeypatch):
    stream = chat_service.create_stream("general", "q")
    _send_with_tool(chat, stream["id"], "think_deeply", monkeypatch)
    status = _model_view_of_next_turn(stream["id"], monkeypatch)["text"]
    assert "Claude is working on it" in status and "Nothing is running" not in status


def test_the_system_prompt_stays_the_same_so_ollama_can_reuse_its_cache(chat, monkeypatch):
    # Measured: a changed prompt start costs ~78 s of re-reading on the M1; an unchanged one 0.5 s.
    stream = chat_service.create_stream("general", "q")
    # Ollama's template hoists every system message to the top, so the status
    # can't be one: it rides in the user turn, at the end of the prompt.
    idle = _model_view_of_next_turn(stream["id"], monkeypatch)
    _send_with_tool(chat, stream["id"], "think_deeply", monkeypatch)
    busy = _model_view_of_next_turn(stream["id"], monkeypatch)
    assert idle["prompt"] == busy["prompt"]
    assert all(m["role"] != "system" for m in idle["history"] + busy["history"])
