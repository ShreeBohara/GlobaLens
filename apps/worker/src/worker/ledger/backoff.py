"""How long a file that just failed waits before it is tried again.

A file that is listed can return 404 for some minutes, so the first retries come quickly. A
file that stays missing is asked for four times an hour, which is about 670 requests over the
7 days after which it becomes a gap.
"""

from datetime import timedelta

__all__ = ["BASE", "CAP", "delay"]

BASE = timedelta(seconds=30)
CAP = timedelta(minutes=15)


def delay(attempts: int) -> timedelta:
    """The wait after a file's `attempts`-th lease failed: 30 s, doubling, capped at 15 min."""
    if attempts < 1:
        raise ValueError("a failure is at least the first attempt")
    doublings = min(attempts - 1, 16)  # past the cap long before 2**16, and the number stays small
    return min(CAP, BASE * 2**doublings)
