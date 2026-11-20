"""The publisher process: it takes the lock, then runs a pass every PASS_SECONDS until stopped.

    GL_DATABASE_URL=postgresql://worker@127.0.0.1:5432/globalens \\
    GL_STORE_DIR=/path/outside/the/repository \\
    python -m worker publish

A second publisher cannot take the lock and exits at once with EXIT_LOCKED. If a pass is
overtaken by a later one, another publisher is running without the lock: the process stops with
EXIT_FENCED rather than race it. A pass that fails is logged and tried again after PASS_SECONDS;
a broken database connection ends the process.

After each committed pass it pings Healthchecks.io's dead-man switch at GL_HEALTHCHECK_URL, so a
`now.json` that stops moving pages someone (docs/design/p1.md §15). With no URL configured it
pings nothing. A ping URL is a secret: it is never logged.

The passes are the ledger's (`worker.ledger.publish`); this module only runs them.
"""

import logging
import threading
import urllib.request
from collections.abc import Callable
from typing import Any

from worker.dataplane import DataPlane, lake_reader
from worker.ledger import publish
from worker.ledger.fence import Connection
from worker.ledger.publish import Outcome
from worker.store import ObjectStore

__all__ = ["EXIT_FENCED", "EXIT_LOCKED", "PASS_SECONDS", "ping", "serve"]

log = logging.getLogger(__name__)

PASS_SECONDS = 30.0
"""How long the publisher waits after a pass that had nothing to do."""

EXIT_LOCKED = 3
"""The exit status of a publisher that found another holding the lock."""

EXIT_FENCED = 4
"""The exit status of a publisher whose pass was overtaken by another publisher's."""

PING_SECONDS = 10.0

Opener = Callable[..., Any]


def ping(url: str | None, *, opener: Opener = urllib.request.urlopen) -> bool:
    """Ping the dead-man switch. Does nothing without a URL. Never raises: a failed ping must
    not stop publishing, and the next commit pings again. Only the error's type is logged,
    because its message can hold the URL."""
    if not url:
        return False
    try:
        with opener(url, timeout=PING_SECONDS):
            pass
    except Exception as error:
        log.warning("the Healthchecks.io ping failed: %s", type(error).__name__)
        return False
    return True


def serve(
    conn: Connection,
    store: ObjectStore,
    stop: threading.Event,
    *,
    healthcheck_url: str | None = None,
    pass_seconds: float = PASS_SECONDS,
    pinger: Callable[[str | None], bool] = ping,
) -> int:
    """Publish until `stop` is set. Returns the process's exit status."""
    if not publish.lock(conn):
        log.error("another publisher holds the lock; this one exits")
        return EXIT_LOCKED
    plane = DataPlane(lake_reader(store.get))
    while not stop.is_set():
        try:
            result = publish.run(conn, store, plane)
        except Exception:
            if conn.broken:
                raise
            log.exception("a pass failed; trying again in %s seconds", pass_seconds)
            stop.wait(pass_seconds)
            continue
        if result.outcome is Outcome.FENCED:
            log.error("pass %s was overtaken: another publisher is running", result.seq)
            return EXIT_FENCED
        if result.outcome is Outcome.IDLE:
            stop.wait(pass_seconds)
            continue
        writes = result.writes.json() if result.writes is not None else {}
        written = sum(kind["n"] for kind in writes.get("puts", {}).values())
        log.info(
            "pass %s published %d intervals and wrote %d objects",
            result.seq,
            len(result.published),
            written,
        )
        pinger(healthcheck_url)
    return 0
