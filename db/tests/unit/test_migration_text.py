"""What can be said about 0001_ingest.sql without a database.

The checks that need PostgreSQL are in db/tests/pg; these only read the file, so they run under
`mise run check` and catch the cheap mistakes at every turn end.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MIGRATION = ROOT / "db" / "migrations" / "0001_ingest.sql"
ROLES = ROOT / "db" / "roles.sql"


def sections() -> tuple[str, str]:
    text = MIGRATION.read_text(encoding="utf-8")
    assert text.count("-- migrate:up") == 1
    assert text.count("-- migrate:down") == 1
    before, rest = text.split("-- migrate:up", 1)
    up, down = rest.split("-- migrate:down", 1)
    assert not sql_only(before).strip(), "no SQL may come before -- migrate:up"
    return up, down


def sql_only(text: str) -> str:
    """The text without `--` comments, lower-cased, so prose in comments cannot match."""
    return "\n".join(line.split("--", 1)[0] for line in text.splitlines()).lower()


def test_it_is_a_dbmate_file_with_up_before_down() -> None:
    up, down = sections()
    assert "create table ingest.interval" in sql_only(up)
    assert "drop table ingest.interval" in sql_only(down)


def test_phase_2_parts_are_not_in_it() -> None:
    up, _ = sections()
    code = sql_only(up)
    assert "lease_epoch" not in code  # arrives with the standby in Phase 2 (design note §5)
    assert "dead_letter" not in code  # Q12: a `dead` state and `last_error` in Phase 1


def test_it_creates_no_role_and_carries_no_password() -> None:
    up, down = sections()
    code = sql_only(up + down)
    assert not re.search(r"\b(create|alter|drop)\s+(role|user)\b", code)
    assert "password" not in code


def test_roles_sql_sets_no_password_and_makes_no_superuser() -> None:
    code = sql_only(ROLES.read_text(encoding="utf-8"))
    assert "password" not in code
    assert not re.search(r"(?<!no)superuser", code)
    for role in ("worker", "migrator", "readonly"):
        assert re.search(rf"create role {role}\b", code)


def test_down_drops_what_up_creates() -> None:
    up, down = sections()
    created = re.findall(r"create (schema|type|table) ([a-z_.]+)", sql_only(up))
    dropped = re.findall(r"drop (schema|type|table) ([a-z_.]+)", sql_only(down))
    assert created, "the up section creates nothing?"
    assert sorted(dropped) == sorted(created)
    # No `cascade`: a down that would take a later migration's objects with it must fail.
    assert "cascade" not in sql_only(down)
