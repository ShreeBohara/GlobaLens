"""The backoff schedule of a file that keeps failing."""

from datetime import timedelta

import pytest
from worker.ledger import backoff


def test_the_schedule_doubles_from_thirty_seconds_to_a_quarter_of_an_hour() -> None:
    assert [backoff.delay(attempts) for attempts in range(1, 9)] == [
        timedelta(seconds=30),
        timedelta(minutes=1),
        timedelta(minutes=2),
        timedelta(minutes=4),
        timedelta(minutes=8),
        timedelta(minutes=15),
        timedelta(minutes=15),
        timedelta(minutes=15),
    ]


def test_it_never_exceeds_the_cap_however_many_attempts() -> None:
    assert backoff.delay(64) == backoff.CAP
    assert backoff.delay(1_000_000) == backoff.CAP


def test_it_never_shrinks() -> None:
    delays = [backoff.delay(attempts) for attempts in range(1, 40)]
    assert delays == sorted(delays)


@pytest.mark.parametrize("attempts", [0, -1])
def test_a_failure_is_at_least_the_first_attempt(attempts: int) -> None:
    with pytest.raises(ValueError):
        backoff.delay(attempts)


def test_the_first_five_retries_fit_inside_sixteen_minutes() -> None:
    # Listed files have returned 404 for about seven minutes (the research file). The first
    # five retries land inside sixteen minutes, so such a file is picked up soon after it
    # appears and not a whole cap later.
    waited = sum((backoff.delay(n) for n in range(1, 6)), timedelta())
    assert waited == timedelta(minutes=15, seconds=30)
