"""Run the poller or a tier-1 worker from the command line.

    GL_DATABASE_URL=postgresql://worker@127.0.0.1:5432/globalens \\
    GL_STORE_DIR=/path/outside/the/repository \\
    python -m worker poll        # or: work

Both run until interrupted. Any number of `work` processes may run at once: the ledger's leases
keep them apart. This is a local entry point. The node's service units, the role guard in
front of them and the R2 object store arrive with the deploy tasks.
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

from worker import feed, poller
from worker.db import connect
from worker.ledger import tier1
from worker.store import FolderStore

log = logging.getLogger("worker")

IDLE_SECONDS = 2.0  # how long a worker waits when the ledger has nothing ready


def _work(dsn: str, store_dir: Path, stop: threading.Event) -> None:
    store = FolderStore(store_dir)
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
    parser.add_argument("role", choices=["poll", "work"])
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
    else:
        store_dir = os.environ.get("GL_STORE_DIR")
        if not store_dir:
            parser.error("GL_STORE_DIR is not set")
        _work(dsn, Path(store_dir), stop)
    return 0


if __name__ == "__main__":
    sys.exit(main())
