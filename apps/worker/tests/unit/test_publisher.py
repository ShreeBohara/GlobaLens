"""The publisher process's dead-man ping: nothing without a URL, never a raise, never the URL
in a log. No network: the opener is a stand-in."""

import http.client
import logging
import urllib.error
from typing import Any

import pytest
from worker import publisher

SECRET = "https://hc-ping.test/0f1e2d3c-secret-uuid"


class Opener:
    def __init__(self, error: Exception | None = None) -> None:
        self.calls: list[tuple[str, float]] = []
        self.error = error

    def __call__(self, url: str, *, timeout: float) -> Any:
        self.calls.append((url, timeout))
        if self.error is not None:
            raise self.error
        return self

    def __enter__(self) -> "Opener":
        return self

    def __exit__(self, *_: object) -> None:
        return None


def test_without_a_url_nothing_is_pinged() -> None:
    opener = Opener()
    assert not publisher.ping(None, opener=opener)
    assert not publisher.ping("", opener=opener)
    assert opener.calls == []


def test_with_a_url_it_is_pinged_once_with_a_time_limit() -> None:
    opener = Opener()
    assert publisher.ping(SECRET, opener=opener)
    assert opener.calls == [(SECRET, publisher.PING_SECONDS)]


@pytest.mark.parametrize(
    "error",
    [
        urllib.error.URLError("no route"),
        TimeoutError(),
        ValueError("bad url"),
        http.client.BadStatusLine("garbage"),
        http.client.LineTooLong("header line"),
        http.client.InvalidURL(f"URL can't contain control characters. {SECRET!r}"),
        RuntimeError("anything else"),
    ],
)
def test_a_failed_ping_is_logged_without_the_url_and_never_raises(
    error: Exception, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING, logger="worker.publisher"):
        assert not publisher.ping(SECRET, opener=Opener(error))
    assert "ping failed" in caplog.text
    assert "hc-ping" not in caplog.text and "secret" not in caplog.text
