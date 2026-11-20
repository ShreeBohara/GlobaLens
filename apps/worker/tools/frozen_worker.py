"""Show the fence on a live ledger: a worker that freezes for longer than its lease.

    GL_DATABASE_URL=postgresql://worker@127.0.0.1:5432/globalens \\
    GL_STORE_DIR=/path/outside/the/repository \\
    uv run python apps/worker/tools/frozen_worker.py --seconds 330

Run it beside a poller and at least one ordinary worker (`python -m worker`). It works like
any worker until a walk reaches the commit named by `--commit` (by default the first one of a
file that downloaded, `listed` to `fetched`; `any` takes whichever commit comes first, which
for a file that is not there yet is its release). Just before that commit it stops its own
process with SIGSTOP: no code runs, as in a paused container or a stalled machine. A helper
process wakes it after `--seconds`. By then its lease has run out, another worker has taken
the file, and the commit this one makes on waking changes no row.

It exits 0 if the commit was rejected, and 1 if it was not.
"""

import argparse
import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from worker import feed
from worker.db import connect
from worker.ledger import tier1
from worker.ledger.fence import Connection, Lease, State
from worker.store import FolderStore

log = logging.getLogger("frozen")

ROW = """
select state::text, lease_token, lease_until, attempts
  from ingest.interval where (stream, stamp) = (%s::ingest.stream, %s)
"""


def describe(conn: Connection, held: Lease) -> str:
    row = conn.execute(ROW, (held.stream.value, held.stamp)).fetchone()
    assert row is not None
    state, token, until, attempts = row
    whose = "nobody's" if token is None else "this worker's" if token == held.token else "another's"
    return f"state={state} token={whose} lease_until={until} attempts={attempts}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=int, default=330, help="how long to stay frozen")
    parser.add_argument(
        "--commit",
        choices=["any", "fetched", "verified", "loaded"],
        default="fetched",
        help="freeze just before the commit to this state",
    )
    arguments = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)sZ %(levelname)s %(name)s [%(process)d] %(message)s"
    )
    logging.Formatter.converter = time.gmtime

    target = None if arguments.commit == "any" else State(arguments.commit)
    store = FolderStore(Path(os.environ["GL_STORE_DIR"]))
    with connect(os.environ["GL_DATABASE_URL"]) as conn:
        while True:
            steps = tier1.walk(conn, store, feed.http_get)
            try:
                at = next(steps)
            except StopIteration:
                time.sleep(1.0)  # nothing to lease yet
                continue
            held = at.lease
            log.info(
                "leased %s %s as %s; row: %s",
                held.stream,
                held.stamp,
                held.state,
                describe(conn, held),
            )
            try:
                while not (at.point is tier1.Point.COMMIT and (target is None or at.to is target)):
                    at = next(steps)
            except StopIteration as done:
                log.info("that walk ended before the commit (%s); on to the next file", done.value)
                continue
            break

        log.info("about to commit %s to %s; freezing for %d s", at.was, at.to, arguments.seconds)
        waker = f"sleep {arguments.seconds}; kill -CONT {os.getpid()}"
        subprocess.Popen(["/bin/sh", "-c", waker], start_new_session=True)
        frozen_at = time.monotonic()
        os.kill(os.getpid(), signal.SIGSTOP)  # nothing below runs until SIGCONT arrives
        log.info("awake after %.0f s; row: %s", time.monotonic() - frozen_at, describe(conn, held))

        before = describe(conn, held)
        try:
            next(steps)
        except StopIteration as done:
            outcome = done.value
        else:
            outcome = None
        after = describe(conn, held)
        if outcome is tier1.Outcome.FENCED and after == before:
            log.info("the commit changed no row: FENCED. The row is as it was: %s", after)
            return 0
        log.error("the commit was not rejected (outcome %s); row: %s", outcome, after)
        return 1


if __name__ == "__main__":
    sys.exit(main())
