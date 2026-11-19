"""0001_ingest.sql against a clean PostgreSQL 18.

One throwaway container per test run (the image is pinned by digest below). Each database in it
is prepared the way production is: `db/roles.sql` as the cluster's superuser, then dbmate as the
role `migrator`, which is not a superuser. Queries run through `psql` inside the container, so
the only things this needs on the machine are Docker and the dbmate that mise pins.

These tests need Docker, so they are not part of `mise run check`. They run under
`mise run test` and `mise run test:db`. With Docker down they fail; they never skip.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pytest

ROOT = Path(__file__).resolve().parents[3]
ROLES_SQL = ROOT / "db" / "roles.sql"
SEEDGEN = ROOT / "db" / "seedgen.py"

# PostgreSQL 18.6 on Debian trixie: the multi-platform index (linux/amd64 and linux/arm64), so
# the same pin serves both node architectures and CI. Why this one: docs/adr/0007.
# GL_TEST_PG_IMAGE points the same tests at another image, such as the one task 7 builds.
PG_IMAGE = os.environ.get(
    "GL_TEST_PG_IMAGE",
    "postgres:18.6-trixie@sha256:e3d24f6906d0760bf4da0dae872415391ededefad23fd471c47dc53b0ddf3c42",
)

STATES = ["listed", "fetched", "verified", "loaded", "published", "gap", "dead"]
STREAMS = ["english", "translated"]
INGEST_TABLES = ["ingest.interval", "ingest.known_gap", "ingest.publish_pass"]
ALL_TABLES = [*INGEST_TABLES, "prov.source"]
ROLES = ["worker", "migrator", "readonly"]

CHECK_VIOLATION = "23514"
UNIQUE_VIOLATION = "23505"
INSUFFICIENT_PRIVILEGE = "42501"

# Quiet, unaligned, tuples only; stop at the first error and print its SQLSTATE.
PSQL = ["psql", "-X", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1", "-v", "VERBOSITY=verbose"]

A_ROW = "('english', timestamptz '{stamp}', 'https://example.org/x.zip', now())"
INSERT_INTERVAL = f"insert into ingest.interval (stream, stamp, url, listed_at) values {A_ROW}"


def run(
    command: list[str], *, stdin: str | None = None, timeout: int = 120
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command, input=stdin, capture_output=True, encoding="utf-8", timeout=timeout, check=False
    )


@dataclass(frozen=True)
class Server:
    """The container, and the port its PostgreSQL listens on at 127.0.0.1."""

    container: str
    port: int

    def psql(
        self, sql: str, *, database: str, role: str = "postgres"
    ) -> subprocess.CompletedProcess[str]:
        """Run SQL from stdin. A failing statement stops the script and prints its SQLSTATE."""
        command = ["docker", "exec", "-i", "-e", "PGTZ=UTC", self.container, *PSQL]
        return run([*command, "-U", role, "-d", database, "-f", "-"], stdin=sql)


@dataclass(frozen=True)
class Database:
    server: Server
    name: str

    def run_sql(self, sql: str, *, role: str = "postgres") -> subprocess.CompletedProcess[str]:
        return self.server.psql(sql, database=self.name, role=role)

    def execute(self, sql: str, *, role: str = "postgres") -> None:
        result = self.run_sql(sql, role=role)
        assert result.returncode == 0, result.stderr

    def query(self, sql: str, *, role: str = "postgres") -> list[dict[str, Any]]:
        result = self.run_sql(
            f"select coalesce(json_agg(q), '[]'::json) from ({sql}) as q", role=role
        )
        assert result.returncode == 0, result.stderr
        return cast("list[dict[str, Any]]", json.loads(result.stdout))

    def column(self, sql: str, *, role: str = "postgres") -> list[Any]:
        """The values of a one-column query."""
        return [next(iter(row.values())) for row in self.query(sql, role=role)]

    def refuses(self, sql: str, sqlstate: str, *, role: str = "postgres") -> str:
        """Assert that the SQL fails with this SQLSTATE, and return the error text.

        It runs in a transaction that is rolled back, so SQL that is wrongly accepted leaves
        nothing behind to fail other tests for the wrong reason.
        """
        result = self.run_sql(f"begin; {sql.rstrip().rstrip(';')}; rollback;", role=role)
        assert result.returncode != 0, f"expected SQLSTATE {sqlstate}, but this succeeded:\n{sql}"
        assert f"ERROR:  {sqlstate}:" in result.stderr, result.stderr
        return result.stderr

    def dbmate(self, *args: str) -> subprocess.CompletedProcess[str]:
        """Run dbmate from the repository root as `migrator`, with a clean environment."""
        dbmate = shutil.which("dbmate")
        assert dbmate, "dbmate is not on PATH. Run these tests with `mise run test:db`."
        url = f"postgres://migrator@127.0.0.1:{self.server.port}/{self.name}?sslmode=disable"
        return subprocess.run(
            [dbmate, "--url", url, "--migrations-dir", "db/migrations", "--no-dump-schema", *args],
            cwd=ROOT,
            env={"PATH": os.environ["PATH"], "HOME": os.environ.get("HOME", "/")},
            capture_output=True,
            encoding="utf-8",
            timeout=120,
            check=False,
        )

    def up(self) -> None:
        result = self.dbmate("up")
        assert result.returncode == 0, result.stdout + result.stderr


@pytest.fixture(scope="session")
def server() -> Iterator[Server]:
    if run(["docker", "info"], timeout=30).returncode != 0:
        pytest.fail(
            "Docker is not running, and the SQL tests need it (start it with `open -ga Docker`).",
            pytrace=False,
        )
    container = f"globalens-sqltest-{uuid.uuid4().hex[:12]}"
    command = ["docker", "run", "--detach", "--rm", "--name", container]
    command += ["--label", "globalens.sqltest=1"]
    # Trust authentication: no password exists anywhere, the port is bound to this machine
    # only, and the container lives for one test run.
    command += ["--env", "POSTGRES_HOST_AUTH_METHOD=trust", "--publish", "127.0.0.1::5432"]
    started = run([*command, PG_IMAGE], timeout=600)
    assert started.returncode == 0, started.stderr
    try:
        wait_until_ready(container)
        published = run(["docker", "port", container, "5432/tcp"])
        assert published.returncode == 0, published.stderr
        port = int(published.stdout.splitlines()[0].rsplit(":", 1)[1])
        yield Server(container=container, port=port)
    finally:
        run(["docker", "rm", "--force", "--volumes", container])


def wait_until_ready(container: str, seconds: int = 90) -> None:
    """Wait for the real server. Over TCP, so the image's set-up server does not count."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        ready = ["pg_isready", "-q", "-h", "127.0.0.1", "-U", "postgres"]
        if run(["docker", "exec", container, *ready]).returncode == 0:
            return
        time.sleep(0.5)
    logs = run(["docker", "logs", "--tail", "40", container])
    pytest.fail(f"PostgreSQL was not ready after {seconds} s:\n{logs.stdout}{logs.stderr}")


def new_database(server: Server) -> Database:
    """A new, empty database prepared as production is: db/roles.sql run by the superuser."""
    name = f"t_{uuid.uuid4().hex[:12]}"
    created = server.psql(f"create database {name};", database="postgres")
    assert created.returncode == 0, created.stderr
    database = Database(server=server, name=name)
    database.execute(ROLES_SQL.read_text(encoding="utf-8"))
    return database


@pytest.fixture(scope="session")
def db(server: Server) -> Database:
    """One migrated database shared by the tests that only read (or roll back)."""
    database = new_database(server)
    database.up()
    return database


@pytest.fixture
def empty_db(server: Server) -> Database:
    """A database of its own, not yet migrated, for the tests that change the schema."""
    return new_database(server)


@pytest.fixture(scope="session")
def expected_seed() -> dict[str, list[dict[str, Any]]]:
    """The seed rows as the generator reads them from prov/sources.yml and the script output."""
    result = run([sys.executable, str(SEEDGEN), "json"])
    assert result.returncode == 0, result.stderr
    return cast("dict[str, list[dict[str, Any]]]", json.loads(result.stdout))


# --- the migration applies, as a role that is not a superuser --------------------------------


def test_the_server_is_postgresql_18(db: Database) -> None:
    (version,) = db.column("select current_setting('server_version_num')::int")
    assert 180000 <= version < 190000


def test_up_applies_0001_and_dbmate_records_it(db: Database) -> None:
    assert db.column("select version from public.schema_migrations") == ["0001"]
    status = db.dbmate("status")
    assert status.returncode == 0, status.stderr
    assert "[X] 0001_ingest.sql" in status.stdout
    assert "Pending: 0" in status.stdout


def test_up_again_changes_nothing(db: Database) -> None:
    db.up()
    assert db.column("select version from public.schema_migrations") == ["0001"]


def test_everything_belongs_to_migrator_and_no_role_is_a_superuser(db: Database) -> None:
    owners = db.query(
        "select schemaname || '.' || tablename as name, tableowner as owner from pg_tables"
        " where schemaname in ('ingest', 'prov') order by 1"
    )
    assert owners == [{"name": name, "owner": "migrator"} for name in sorted(ALL_TABLES)]
    assert db.column(
        "select nspowner::regrole::text from pg_namespace"
        " where nspname in ('ingest', 'prov') order by nspname"
    ) == ["migrator", "migrator"]

    roles = db.query(
        "select rolname, rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls"
        " from pg_roles where rolname in ('worker', 'migrator', 'readonly') order by rolname"
    )
    assert [role["rolname"] for role in roles] == sorted(ROLES)
    for role in roles:
        flags = {key: value for key, value in role.items() if key != "rolname"}
        assert not any(flags.values()), role


def test_roles_sql_can_run_again_and_corrects_a_role_that_drifted(empty_db: Database) -> None:
    empty_db.execute("alter role readonly createdb createrole nologin;")
    empty_db.execute(ROLES_SQL.read_text(encoding="utf-8"))
    drifted = empty_db.column(
        "select rolname from pg_roles where rolname in ('worker', 'migrator', 'readonly')"
        " and (rolsuper or rolcreatedb or rolcreaterole or rolreplication or rolbypassrls"
        " or not rolcanlogin)"
    )
    assert drifted == []
    owner = empty_db.column(
        "select datdba::regrole::text from pg_database where datname = current_database()"
    )
    assert owner == ["migrator"]


def test_roles_sql_refuses_the_maintenance_database(server: Server) -> None:
    # Run against `postgres` by mistake, it must not hand that database to migrator.
    result = server.psql(ROLES_SQL.read_text(encoding="utf-8"), database="postgres")
    assert result.returncode != 0
    assert "application database" in result.stderr
    owner = server.psql(
        "select datdba::regrole::text from pg_database where datname = 'postgres';",
        database="postgres",
    )
    assert owner.stdout.strip() == "postgres"


def test_down_then_up_applies_again(empty_db: Database, expected_seed: dict[str, Any]) -> None:
    empty_db.up()

    down = empty_db.dbmate("down")
    assert down.returncode == 0, down.stdout + down.stderr
    assert empty_db.column("select version from public.schema_migrations") == []
    schemas = empty_db.column(
        "select nspname from pg_namespace where nspname in ('ingest', 'prov')"
    )
    assert schemas == []
    types = empty_db.column(
        "select t.typname from pg_type t join pg_namespace n on n.oid = t.typnamespace"
        " where t.typname in ('stream', 'state') and n.nspname not like 'pg\\_%'"
    )
    assert types == []
    # The roles belong to the cluster, not to the migration: a down leaves them.
    roles = empty_db.column(
        "select rolname from pg_roles where rolname in ('worker', 'migrator', 'readonly')"
    )
    assert len(roles) == 3

    empty_db.up()
    assert empty_db.column("select version from public.schema_migrations") == ["0001"]
    gaps = empty_db.column("select count(*) from ingest.known_gap")
    sources = empty_db.column("select count(*) from prov.source")
    assert gaps == [len(expected_seed["ingest.known_gap"])]
    assert sources == [len(expected_seed["prov.source"])]


# --- the shape of design note §5 ---------------------------------------------------------------


def test_the_state_enum_has_exactly_the_states_of_section_5(db: Database) -> None:
    assert db.column("select unnest(enum_range(null::ingest.state))::text") == STATES


def test_the_stream_enum_has_the_two_streams(db: Database) -> None:
    assert db.column("select unnest(enum_range(null::ingest.stream))::text") == STREAMS


def columns(db: Database, table: str) -> list[tuple[str, str, bool]]:
    """(name, type, nullable) for each column, in order."""
    rows = db.query(
        "select attname as name, format_type(atttypid, atttypmod) as type,"
        " not attnotnull as nullable from pg_attribute"
        f" where attrelid = '{table}'::regclass and attnum > 0 and not attisdropped"
        " order by attnum"
    )
    return [(row["name"], row["type"], row["nullable"]) for row in rows]


def test_interval_has_the_columns_of_section_5(db: Database) -> None:
    tz = "timestamp with time zone"
    assert columns(db, "ingest.interval") == [
        ("stream", "ingest.stream", False),
        ("stamp", tz, False),
        ("url", "text", False),
        ("size", "bigint", True),
        ("md5", "text", True),
        ("state", "ingest.state", False),
        ("attempts", "integer", False),
        ("next_attempt_at", tz, False),
        ("lease_token", "uuid", True),
        ("lease_until", tz, True),
        ("seq", "bigint", True),
        ("rows", "integer", True),
        ("raw_key", "text", True),
        ("parquet_key", "text", True),
        ("listed_at", tz, False),
        ("loaded_at", tz, True),
        ("published_at", tz, True),
        ("last_error", "text", True),
    ]


def test_the_other_tables_have_the_columns_of_section_5(db: Database) -> None:
    tz = "timestamp with time zone"
    assert columns(db, "ingest.known_gap") == [
        ("stream", "ingest.stream", False),
        ("first_stamp", tz, False),
        ("last_stamp", tz, False),
        ("intervals", "integer", False),
        ("reason", "text", False),
        ("recorded_at", tz, False),
    ]
    assert columns(db, "prov.source") == [
        ("source_id", "text", False),
        ("licence", "text", False),
        ("redistribute_ok", "boolean", False),
        ("share_alike", "boolean", False),
        ("nc", "boolean", False),
        ("attribution_text", "text", False),
        ("verified_on", "date", False),
    ]
    assert columns(db, "ingest.publish_pass") == [
        ("seq", "bigint", False),
        ("manifest_key", "text", True),
        ("started_at", tz, False),
        ("finished_at", tz, True),
        ("objects", "jsonb", True),
    ]


def test_only_the_four_tables_exist(db: Database) -> None:
    assert db.column(
        "select schemaname || '.' || tablename from pg_tables"
        " where schemaname in ('ingest', 'prov') order by 1"
    ) == sorted(ALL_TABLES)


@pytest.mark.parametrize(
    ("table", "key"),
    [
        ("ingest.interval", ["stream", "stamp"]),
        ("ingest.known_gap", ["stream", "first_stamp"]),
        ("prov.source", ["source_id"]),
        ("ingest.publish_pass", ["seq"]),
    ],
)
def test_the_primary_keys_exist(db: Database, table: str, key: list[str]) -> None:
    columns_of_key = db.column(
        "select a.attname from pg_index i"
        " cross join lateral unnest(i.indkey) with ordinality as k(attnum, position)"
        " join pg_attribute a on a.attrelid = i.indrelid and a.attnum = k.attnum"
        f" where i.indrelid = '{table}'::regclass and i.indisprimary order by k.position"
    )
    assert columns_of_key == key


def test_the_partial_index_on_claimable_intervals_exists(db: Database) -> None:
    indexes = db.query(
        "select c.relname as name, pg_get_expr(i.indpred, i.indrelid) as predicate,"
        " (select array_agg(a.attname order by k.position)"
        "    from unnest(i.indkey) with ordinality as k(attnum, position)"
        "    join pg_attribute a on a.attrelid = i.indrelid and a.attnum = k.attnum) as columns"
        " from pg_index i join pg_class c on c.oid = i.indexrelid"
        " where i.indrelid = 'ingest.interval'::regclass and not i.indisprimary"
    )
    assert len(indexes) == 1, indexes
    (index,) = indexes
    assert index["columns"] == ["next_attempt_at"]
    assert index["predicate"] is not None, "the index must be partial"
    # The states a tier-1 worker may lease (§7.3), and no others.
    claimable = set(re.findall(r"'(\w+)'::ingest\.state", index["predicate"]))
    assert claimable == {"listed", "fetched", "verified"}


# --- the 15-minute stamp check -----------------------------------------------------------------


@pytest.mark.parametrize(
    "stamp",
    [
        "2026-11-15 12:00:00+00",
        "2026-11-15 12:15:00+00",
        "2026-11-15 12:30:00+00",
        "2026-11-15 12:45:00+00",
        "2026-11-15 18:00:00+05:45",  # 12:15 UTC, written with Kathmandu's offset
    ],
)
def test_the_stamp_check_accepts_a_quarter_hour(db: Database, stamp: str) -> None:
    db.execute(f"begin; {INSERT_INTERVAL.format(stamp=stamp)}; rollback;", role="worker")


@pytest.mark.parametrize(
    "stamp",
    [
        "2026-11-15 12:07:00+00",
        "2026-11-15 12:14:59+00",
        "2026-11-15 12:15:01+00",
        "2026-11-15 12:15:00.000001+00",
        "2026-11-15 12:20:00+00",
    ],
)
def test_the_stamp_check_rejects_an_unaligned_stamp(db: Database, stamp: str) -> None:
    error = db.refuses(INSERT_INTERVAL.format(stamp=stamp), CHECK_VIOLATION, role="worker")
    assert "interval_stamp_check" in error


def test_the_stamp_check_does_not_depend_on_the_session_time_zone(db: Database) -> None:
    for zone in ("Asia/Kathmandu", "America/St_Johns", "UTC"):
        aligned = INSERT_INTERVAL.format(stamp="2026-11-15 12:15:00+00")
        unaligned = INSERT_INTERVAL.format(stamp="2026-11-15 12:20:00+00")
        db.execute(f"set timezone = '{zone}'; begin; {aligned}; rollback;", role="worker")
        db.refuses(f"set timezone = '{zone}'; {unaligned}", CHECK_VIOLATION, role="worker")


def test_an_update_cannot_move_a_stamp_off_the_grid(db: Database) -> None:
    db.refuses(
        f"{INSERT_INTERVAL.format(stamp='2026-11-15 12:15:00+00')};"
        " update ingest.interval set stamp = stamp + interval '1 minute'",
        CHECK_VIOLATION,
        role="worker",
    )


# --- defaults and the key ------------------------------------------------------------------------


def test_a_new_interval_starts_listed_with_no_lease(db: Database) -> None:
    result = db.run_sql(
        f"begin; {INSERT_INTERVAL.format(stamp='2026-11-15 12:15:00+00')};"
        " select row_to_json(i) from ingest.interval i; rollback;",
        role="worker",
    )
    assert result.returncode == 0, result.stderr
    row = json.loads(result.stdout)
    assert row["state"] == "listed"
    assert row["attempts"] == 0
    assert row["next_attempt_at"] is not None
    unset = ["size", "md5", "lease_token", "lease_until", "seq", "rows", "raw_key", "parquet_key"]
    unset += ["loaded_at", "published_at", "last_error"]
    assert {name: row[name] for name in unset} == dict.fromkeys(unset)


def test_listing_the_same_stamp_twice_keeps_one_row(db: Database) -> None:
    insert = INSERT_INTERVAL.format(stamp="2026-11-15 12:15:00+00")
    db.refuses(f"{insert}; {insert}", UNIQUE_VIOLATION, role="worker")
    # The poller's form (§7.5): the second insert is not an error and adds nothing.
    result = db.run_sql(
        f"begin; {insert} on conflict do nothing; {insert} on conflict do nothing;"
        " select count(*) from ingest.interval; rollback;",
        role="worker",
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "1"


def test_the_same_stamp_is_a_different_interval_in_each_stream(db: Database) -> None:
    english = INSERT_INTERVAL.format(stamp="2026-11-15 12:15:00+00")
    translated = english.replace("'english'", "'translated'")
    db.execute(f"begin; {english}; {translated}; rollback;", role="worker")


# --- the seeds -----------------------------------------------------------------------------------


def test_the_june_2025_gap_is_seeded_for_both_streams(
    db: Database, expected_seed: dict[str, list[dict[str, Any]]]
) -> None:
    rows = db.query(
        "select stream::text, first_stamp, last_stamp, intervals, reason"
        " from ingest.known_gap order by stream"
    )
    assert rows == expected_seed["ingest.known_gap"]
    assert [row["stream"] for row in rows] == STREAMS
    # Each row's count agrees with its two ends, and both ends are on the 15-minute grid.
    assert db.column(
        "select count(*) from ingest.known_gap"
        " where intervals = extract(epoch from last_stamp - first_stamp) / 900 + 1"
        "   and first_stamp = date_bin('15 minutes', first_stamp, timestamptz 'epoch')"
        "   and last_stamp = date_bin('15 minutes', last_stamp, timestamptz 'epoch')"
    ) == [2]
    assert db.column("select count(*) from ingest.known_gap where recorded_at is null") == [0]


def test_prov_source_is_seeded_from_sources_yml(
    db: Database, expected_seed: dict[str, list[dict[str, Any]]]
) -> None:
    rows = db.query(
        "select source_id, licence, redistribute_ok, share_alike, nc, attribution_text,"
        " verified_on from prov.source"
    )
    by_id = {row["source_id"]: row for row in rows}
    expected = {row["source_id"]: row for row in expected_seed["prov.source"]}
    assert by_id == expected
    assert set(by_id) == {"gdelt-gkg-2.1", "natural-earth", "protomaps-basemap", "openfreemap"}


def test_the_ledger_and_the_pass_log_start_empty(db: Database) -> None:
    assert db.column("select count(*) from ingest.interval") == [0]
    assert db.column("select count(*) from ingest.publish_pass") == [0]


# --- the roles of §5 -----------------------------------------------------------------------------


def privileges(db: Database, role: str, table: str) -> set[str]:
    kinds = ["SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER"]
    checks = ", ".join(
        f"has_table_privilege('{role}', '{table}', '{kind}') as \"{kind}\"" for kind in kinds
    )
    (row,) = db.query(f"select {checks}")
    return {kind for kind, held in row.items() if held}


def test_worker_reads_and_writes_the_ingest_tables_and_nothing_else(db: Database) -> None:
    for table in INGEST_TABLES:
        assert privileges(db, "worker", table) == {"SELECT", "INSERT", "UPDATE"}, table
    assert privileges(db, "worker", "prov.source") == set()
    assert db.column("select has_schema_privilege('worker', 'prov', 'USAGE')") == [False]


def test_readonly_only_reads(db: Database) -> None:
    for table in ALL_TABLES:
        assert privileges(db, "readonly", table) == {"SELECT"}, table


def test_only_migrator_may_create_in_the_schemas(db: Database) -> None:
    rows = db.query(
        "select r as role, s as schema, has_schema_privilege(r, s, 'CREATE') as may_create,"
        " has_schema_privilege(r, s, 'USAGE') as may_use"
        " from unnest(array['worker', 'migrator', 'readonly']) as r,"
        " unnest(array['ingest', 'prov']) as s"
    )
    for row in rows:
        assert row["may_create"] == (row["role"] == "migrator"), row
    used = {(row["role"], row["schema"]) for row in rows if row["may_use"]}
    assert used == {
        ("migrator", "ingest"),
        ("migrator", "prov"),
        ("worker", "ingest"),
        ("readonly", "ingest"),
        ("readonly", "prov"),
    }


def test_the_grants_hold_when_each_role_connects(db: Database) -> None:
    insert = INSERT_INTERVAL.format(stamp="2026-11-15 12:15:00+00")

    # worker: the ledger's writes, but no delete and nothing in prov.
    db.execute(
        f"begin; {insert}; update ingest.interval set state = 'fetched';"
        " insert into ingest.publish_pass (seq) values (1);"
        " insert into ingest.known_gap (stream, first_stamp, last_stamp, intervals, reason)"
        " values ('english', '2026-01-01 00:00+00', '2026-01-01 00:00+00', 1, 'test');"
        " rollback;",
        role="worker",
    )
    db.refuses("delete from ingest.interval", INSUFFICIENT_PRIVILEGE, role="worker")
    db.refuses("select * from prov.source", INSUFFICIENT_PRIVILEGE, role="worker")
    db.refuses("create table ingest.extra (x int)", INSUFFICIENT_PRIVILEGE, role="worker")

    # readonly: reads all four tables and writes none.
    for table in ALL_TABLES:
        db.execute(f"select count(*) from {table}", role="readonly")
    db.refuses(insert, INSUFFICIENT_PRIVILEGE, role="readonly")
    db.refuses("update prov.source set nc = true", INSUFFICIENT_PRIVILEGE, role="readonly")
    db.refuses("delete from ingest.known_gap", INSUFFICIENT_PRIVILEGE, role="readonly")
