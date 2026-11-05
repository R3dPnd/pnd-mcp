"""What the local model reads of a chat's history: older long messages
(Claude's earlier answers) are excerpted so the conversation fits the
model's context and stays fast to read; the latest one stays whole, since
follow-ups are usually about it. The full text stays in the chat, and
think_deeply reads it in full from disk."""

from app.services.chat_service import _model_history

OLD = ("# Thesis plan\n\nShort answer: take TCSS 558 first.\n\n" + "Prose that can go. " * 200 +
       "\n\n## Schedule\n\n| Quarter | Course |\n|---|---|\n| Spring 2027 | **TCSS 555 Machine Learning** |\n\n"
       "**Graduate:** Autumn 2029\n\n" + "More prose. " * 100)
NEW = "# Advisors\n\nReach out next quarter. " + "More. " * 400


def _h():
    return [{"role": "assistant", "content": OLD}, {"role": "user", "content": "and advisors?"},
            {"role": "assistant", "content": NEW}, {"role": "user", "content": "thanks"}]


def test_short_messages_pass_through_unchanged():
    h = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "Hello!"}]
    assert _model_history(h) == h


def test_the_latest_long_message_stays_whole():
    # Measured: excerpting it made the model invent course details it was asked about.
    assert _model_history(_h())[2]["content"] == NEW


def test_older_long_messages_keep_their_opening_and_key_lines():
    # Measured: a plain opening excerpt lost "Spring 2027 → TCSS 555" and the
    # model guessed TCSS 556. Facts live in headings, table rows and bold lines.
    m = _model_history(_h())[0]["content"]
    assert m.startswith("# Thesis plan")
    for line in ("## Schedule", "| Quarter | Course |", "| Spring 2027 | **TCSS 555 Machine Learning** |",
                 "**Graduate:** Autumn 2029"):
        assert line in m
    assert "Prose that can go." not in m and "|---|" not in m


def test_a_digest_is_capped():
    huge = "# T\n\n" + "\n".join(f"| row {i} | **course {i}** |" for i in range(500))
    h = [{"role": "assistant", "content": huge}, {"role": "assistant", "content": NEW}]
    assert len(_model_history(h)[0]["content"]) < 2400


def test_the_excerpt_says_where_the_rest_is_and_not_to_guess():
    m = _model_history(_h())[0]
    assert f"{len(OLD)} characters" in m["content"] and "think_deeply" in m["content"]
    assert "don't guess" in m["content"].lower()


def test_excerpts_are_stable_so_the_prompt_cache_keeps_hitting():
    assert _model_history(_h()) == _model_history(_h())


def test_the_original_history_is_not_modified():
    h = _h()
    _model_history(h)
    assert h[0]["content"] == OLD
