"""A real PostgreSQL 18 for the ledger's tests.

The container comes from task 8's harness (`db/tests/pg/test_0001_ingest.py`): the image
pinned there, started with the `docker` command, prepared with `db/roles.sql`, and migrated
by dbmate as the role `migrator`. That file is loaded by path, so the image is still named in
one place. The ledger's code then connects over TCP as the role `worker`, as it will in
production; `admin` is the superuser, for emptying the tables and for reading rows back.

These tests need Docker, so they are not part of `mise run check`. They run under
`mise run test` and `mise run test:ledger`. With Docker down they fail; they never skip.
"""

import importlib.util
import sys
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import psycopg
import pytest
from gdelt import Stream
from psycopg.rows import dict_row
from worker.db import connect as worker_connect

ROOT = Path(__file__).resolve().parents[4]

Connection = psycopg.Connection[tuple[Any, ...]]
Row = dict[str, Any]


def _load_harness() -> Any:
    path = ROOT / "db" / "tests" / "pg" / "test_0001_ingest.py"
    spec = importlib.util.spec_from_file_location("globalens_sql_harness", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # its dataclasses look their own module up by name
    spec.loader.exec_module(module)
    return module


_harness = _load_harness()

# The harness's session fixture: one throwaway container for the whole run.
server = _harness.server


@dataclass(frozen=True)
class Database:
    """A migrated database in the test container."""

    port: int
    name: str

    def dsn(self, role: str) -> str:
        return f"postgresql://{role}@127.0.0.1:{self.port}/{self.name}"


@pytest.fixture(scope="session")
def database(server: Any) -> Database:
    created = _harness.new_database(server)
    created.up()
    return Database(port=server.port, name=created.name)


@pytest.fixture(scope="session")
def admin(database: Database) -> Iterator[Connection]:
    """The superuser's connection. The ledger's code never uses it."""
    with psycopg.connect(
        database.dsn("postgres"), autocommit=True, options="-c timezone=UTC"
    ) as conn:
        yield conn


@pytest.fixture
def connect(database: Database) -> Iterator[Callable[[], Connection]]:
    """Opens connections as the role `worker`, the way the worker does, and closes them after
    the test. A statement that waits 10 seconds for a lock fails instead of hanging the run."""
    opened: list[Connection] = []

    def open_one() -> Connection:
        conn = worker_connect(database.dsn("worker"))
        conn.execute("set lock_timeout = '10s'")
        opened.append(conn)
        return conn

    yield open_one
    for conn in opened:
        conn.close()


@pytest.fixture
def conn(connect: Callable[[], Connection]) -> Connection:
    return connect()


@pytest.fixture(autouse=True)
def empty_ledger(admin: Connection) -> None:
    """Every test starts with no interval. The seeded gaps of June 2025 stay."""
    admin.execute("truncate ingest.interval")
    admin.execute("delete from ingest.known_gap where first_stamp >= timestamptz '2026-01-01'")


@pytest.fixture
def row(admin: Connection) -> Callable[[Stream, datetime], Row]:
    """Reads one ledger row back, as a dict of its columns."""

    def read(stream: Stream, stamp: datetime) -> Row:
        with admin.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                "select * from ingest.interval where (stream, stamp) = (%s::ingest.stream, %s)",
                (stream.value, stamp),
            )
            found = cursor.fetchone()
        assert found is not None, f"no row for {stream} {stamp}"
        return found

    return read
