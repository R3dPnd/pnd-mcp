"""integrations.job_search.leads — numbering, no repeats, persistence."""

import pytest

from integrations.job_search.leads import Lead, LeadStore, normalize_url


def lead(key, title="SWE", url=None):
    return Lead(key=key, title=title, org="Acme", url=url or f"https://jobs.example/{key}", pay="", location="",
                remote=True, kind="job", score=50, fit="", suggestion="", link="ok")


def test_add_numbers_from_one_and_skips_known(tmp_path):
    store = LeadStore(tmp_path / "leads.json")
    first = store.add([lead("app:1"), lead("app:2"), lead("app:3")], "2026-11-05")
    assert [l.number for l in first] == [1, 2, 3]
    again = store.add([lead("app:1"), lead("app:2"), lead("app:3"), lead("app:4")], "2026-11-05")
    assert [(l.key, l.number) for l in again] == [("app:4", 4)]


def test_numbers_restart_on_a_new_date(tmp_path):
    store = LeadStore(tmp_path / "leads.json")
    store.add([lead("app:1")], "2026-11-05")
    assert [l.number for l in store.add([lead("app:2")], "2026-11-06")] == [1]


def test_by_number_defaults_to_latest_report(tmp_path):
    store = LeadStore(tmp_path / "leads.json")
    store.add([lead("app:1", "Old")], "2026-11-05")
    store.add([lead("app:2", "New")], "2026-11-06")
    assert store.latest_report_date() == "2026-11-06"
    assert store.by_number(1).title == "New"
    assert store.by_number(1, "2026-11-05").title == "Old"
    assert store.by_number(9) is None


def test_same_url_with_utm_is_known(tmp_path):
    store = LeadStore(tmp_path / "leads.json")
    store.add([lead("url:" + normalize_url("https://Jobs.Example/x?utm_source=a#top"))], "2026-11-05")
    assert "url:" + normalize_url("https://jobs.example/x?utm_campaign=b") in store.known_keys()


def test_normalize_url_keeps_meaningful_query():
    assert normalize_url("HTTPS://A.com/p?id=7&utm_medium=x") == "https://a.com/p?id=7"


def test_store_survives_reload_and_status_changes(tmp_path):
    path = tmp_path / "leads.json"
    LeadStore(path).add([lead("app:1")], "2026-11-05")
    reloaded = LeadStore(path)
    reloaded.set_status("app:1", "dismissed")
    assert LeadStore(path).by_number(1).status == "dismissed"


def test_empty_store(tmp_path):
    store = LeadStore(tmp_path / "missing" / "leads.json")
    assert store.known_keys() == set() and store.latest_report_date() is None and store.by_number(1) is None


@pytest.mark.parametrize("variant", [
    "https://www.dataannotation.tech/", "https://www.dataannotation.tech", "https://dataannotation.tech/",
    "HTTPS://DataAnnotation.tech", "https://dataannotation.tech/?utm_source=x",
])
def test_url_variants_of_the_same_page_share_a_key(variant):
    assert normalize_url(variant) == "https://dataannotation.tech/"


def test_trailing_slash_dropped_on_paths():
    assert normalize_url("https://www.opentrain.ai/jobs/go-review/") == "https://opentrain.ai/jobs/go-review"
