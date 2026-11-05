"""Checks the hunt applies in code rather than trusting the model: the pay
floor (with yearly/monthly pay converted to hourly) and whether a lead's link
is real."""

from __future__ import annotations

from collections.abc import Callable

import requests

_HOURS_PER = {"HOUR": 1.0, "DAY": 8.0, "WEEK": 40.0, "MONTH": 173.33, "YEAR": 2080.0}
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def hourly_equivalent(amount: float | None, period: str | None) -> float | None:
    hours = _HOURS_PER.get((period or "").upper())
    if amount is None or hours is None:
        return None
    return amount / hours


def below_pay_floor(salary_min: float | None, salary_max: float | None, period: str | None, floor: float) -> bool:
    """True only when a stated rate (the max if there is one) is under the floor —
    unknown pay is never a reason to drop a lead."""
    hourly = hourly_equivalent(salary_max if salary_max is not None else salary_min, period)
    return hourly is not None and hourly < floor


def check_link(url: str, get: Callable[[str], int]) -> str:
    """"ok", "blocked" (the site refuses bots — the posting may well be real),
    or "dead" (gone, or never existed)."""
    try:
        status = get(url)
    except Exception:
        return "dead"
    if status < 400:
        return "ok"
    if status in (401, 403, 429):
        return "blocked"
    return "dead"


def http_status(url: str) -> int:
    with requests.get(url, headers={"User-Agent": _UA}, timeout=8, allow_redirects=True, stream=True) as resp:
        return resp.status_code
