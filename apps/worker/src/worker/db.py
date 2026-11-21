"""The worker's database connection."""

from typing import Any

import psycopg

__all__ = ["connect"]


def connect(dsn: str) -> psycopg.Connection[tuple[Any, ...]]:
    """A connection as the ledger needs it: autocommit, so each ledger call is its own
    transaction; UTC, so every time read back is in UTC; and READ COMMITTED, PostgreSQL's
    default, stated so that no server setting can change it: the fences rely on each statement
    seeing what was committed before it began (WALKTHROUGH.md)."""
    options = "-c timezone=UTC -c default_transaction_isolation=read\\ committed"
    return psycopg.connect(dsn, autocommit=True, options=options)
