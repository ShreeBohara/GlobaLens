"""Run the poller, a tier-1 worker or the publisher from the command line.

    GL_DATABASE_URL=postgresql://worker@127.0.0.1:5432/globalens \\
    GL_STORE_DIR=/path/outside/the/repository \\
    python -m worker poll        # or: work, publish

All three run until interrupted. Any number of `work` processes may run at once: the ledger's
leases keep them apart. One `publish` process runs: a second one exits (`worker.publisher`).
Optional settings:

    GL_WRITE_LOG=/path/writes.jsonl     one line per object PUT, for the write-budget count
    GL_HEALTHCHECK_URL=https://...      the publisher's dead-man ping; none if unset

This is a local entry point. The node's service units, the role guard in front of them and the
R2 object store arrive with the deploy tasks.
"""

import argparse
import logging
import os
import signal
import sys
import threading
import time
from pathlib import Path
from types import FrameType

from worker import feed, poller, publisher
from worker.db import connect
from worker.ledger import tier1
from worker.store import FolderStore, LoggingStore, ObjectStore

log = logging.getLogger("worker")

IDLE_SECONDS = 2.0  # how long a worker waits when the ledger has nothing ready


def _store(store_dir: Path) -> ObjectStore:
    store = FolderStore(store_dir)
    write_log = os.environ.get("GL_WRITE_LOG")
    return LoggingStore(store, Path(write_log)) if write_log else store


def _work(dsn: str, store: ObjectStore, stop: threading.Event) -> None:
    with connect(dsn) as conn:
        while not stop.is_set():
            try:
                outcome = tier1.run_one(conn, store, feed.http_get)
            except Exception:
                if conn.broken:
                    raise
                # The walk died mid-step. Its lease expires and the step is repeated.
                log.exception("a walk failed; its lease will expire")
                outcome = tier1.Outcome.IDLE
            if outcome is tier1.Outcome.FENCED:
                log.warning("a commit was rejected: the lease had passed to another worker")
            if outcome is tier1.Outcome.IDLE:
                stop.wait(IDLE_SECONDS)


def _poll(dsn: str, stop: threading.Event) -> None:
    with connect(dsn) as conn:
        poller.run(conn, stop)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m worker", description=__doc__)
    parser.add_argument("role", choices=["poll", "work", "publish"])
    arguments = parser.parse_args(argv)

    logging.Formatter.converter = time.gmtime  # log times in UTC, like every stamp
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)sZ %(levelname)s %(name)s [%(process)d] %(message)s",
    )
    dsn = os.environ.get("GL_DATABASE_URL")
    if not dsn:
        parser.error("GL_DATABASE_URL is not set")

    stop = threading.Event()

    def interrupted(signum: int, frame: FrameType | None) -> None:
        stop.set()

    signal.signal(signal.SIGINT, interrupted)
    signal.signal(signal.SIGTERM, interrupted)

    if arguments.role == "poll":
        _poll(dsn, stop)
        return 0
    store_dir = os.environ.get("GL_STORE_DIR")
    if not store_dir:
        parser.error("GL_STORE_DIR is not set")
    store = _store(Path(store_dir))
    if arguments.role == "work":
        _work(dsn, store, stop)
        return 0
    with connect(dsn) as conn:
        return publisher.serve(
            conn, store, stop, healthcheck_url=os.environ.get("GL_HEALTHCHECK_URL") or None
        )


if __name__ == "__main__":
    sys.exit(main())
