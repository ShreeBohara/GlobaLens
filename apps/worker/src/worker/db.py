"""The worker's database connection."""

from typing import Any

import psycopg

__all__ = ["connect"]


def connect(dsn: str) -> psycopg.Connection[tuple[Any, ...]]:
    """A connection as the ledger needs it: autocommit, so each ledger call is its own
    transaction, and UTC, so every time read back is in UTC."""
    return psycopg.connect(dsn, autocommit=True, options="-c timezone=UTC")
