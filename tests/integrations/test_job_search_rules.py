"""integrations.job_search.rules — pay floor and link checks."""

import pytest

from integrations.job_search.rules import below_pay_floor, check_link, hourly_equivalent


def test_yearly_salary_is_converted_before_the_floor():
    # $60k/yr ≈ $28.85/h — above a $25 floor; $40k/yr ≈ $19.23/h — below.
    assert below_pay_floor(60000, None, "YEAR", 25) is False
    assert below_pay_floor(None, 40000, "YEAR", 25) is True


def test_unknown_pay_is_never_below_floor():
    assert below_pay_floor(None, None, None, 25) is False
    assert below_pay_floor(30, None, "FORTNIGHT", 25) is False


def test_hourly_under_floor():
    assert below_pay_floor(18, 22, "HOUR", 25) is True
    assert below_pay_floor(20, 30, "HOUR", 25) is False  # the max counts


@pytest.mark.parametrize("period, amount, hourly", [
    ("HOUR", 30, 30), ("YEAR", 2080 * 25, 25), ("MONTH", 173.33 * 40, 40), ("WEEK", 40 * 35, 35), ("DAY", 8 * 50, 50),
])
def test_hourly_equivalent(period, amount, hourly):
    assert round(hourly_equivalent(amount, period), 2) == hourly


@pytest.mark.parametrize("status, expected", [
    (200, "ok"), (301, "ok"), (403, "blocked"), (429, "blocked"), (401, "blocked"),
    (404, "dead"), (410, "dead"), (500, "dead"), ("raise", "dead"),
])
def test_check_link_classifies(status, expected):
    def get(url):
        if status == "raise":
            raise OSError("dns")
        return status
    assert check_link("https://x.example/job", get) == expected
