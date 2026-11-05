"""integrations.job_search.screening — Claude prompts and parsing."""

import pytest

from integrations.job_search.screening import Screen, gig_prompt, parse_gigs, parse_screen, screen_prompt

CRITERIA = {
    "pay_floor_hourly": 25,
    "schedule": "Async first. Mon-Thu commuting Tacoma->Seattle: no fixed daytime commitments. Fridays flexible.",
    "exclude": ["on-call", "full-time"],
    "kinds": ["part-time SWE", "AI code evaluation/training"],
}


def test_parse_screen_accepts_fenced_json():
    text = 'Here you go:\n```json\n[{"key": "app:1", "keep": true, "score": 82, "fit": "F", "suggestion": "S"}]\n```'
    assert parse_screen(text) == {"app:1": Screen(keep=True, score=82, fit="F", suggestion="S")}


def test_parse_screen_skips_malformed_items():
    text = '[{"key": "app:1", "keep": true, "score": 70, "fit": "F", "suggestion": "S"}, {"keep": true}, "junk"]'
    assert list(parse_screen(text)) == ["app:1"]


def test_parse_screen_raises_on_prose():
    with pytest.raises(ValueError):
        parse_screen("Sorry, I couldn't evaluate these postings.")


def test_screen_prompt_carries_criteria_and_trims_descriptions():
    candidates = [{"key": "app:1", "title": "SWE", "org": "Acme", "pay": "$40/h", "location": "Remote",
                   "remote": True, "description": "x" * 5000}]
    prompt = screen_prompt(candidates, "RESUME TEXT", CRITERIA, "Tacoma, WA")
    assert "Tacoma, WA" in prompt and "25" in prompt and "Mon-Thu" in prompt and "RESUME TEXT" in prompt
    assert "x" * 1501 not in prompt and "x" * 1500 in prompt
    assert '"app:1"' in prompt


def test_gig_prompt_excludes_known_urls():
    prompt = gig_prompt(CRITERIA, "Tacoma, WA", "Full-stack engineer, 8 years", ["https://known.example/a"])
    assert "https://known.example/a" in prompt and "JSON" in prompt


def test_parse_gigs_drops_items_without_urls():
    text = ('[{"title": "Code evaluator", "org": "DataAnnotation", "url": "https://www.dataannotation.tech/", '
            '"pay": "$40/h", "kind": "gig"}, {"title": "No link", "org": "X", "url": "", "kind": "gig"}, '
            '{"title": "Bad", "org": "Y", "url": "ftp://y", "kind": "gig"}]')
    gigs = parse_gigs(text)
    assert [g["org"] for g in gigs] == ["DataAnnotation"]




def test_parse_gigs_handles_citation_markers_around_the_array():
    text = 'I found these [1]: [{"title": "T", "org": "A", "url": "https://a.com", "kind": "gig"}] see [2]'
    assert [g["url"] for g in parse_gigs(text)] == ["https://a.com"]


def test_parse_gigs_distinguishes_no_list_from_empty_list():
    assert parse_gigs("[]") == []
    assert parse_gigs("I couldn't find any open gigs today.") is None
