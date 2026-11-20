"""Object keys derived from content.

Everything a tier-1 worker writes outside the database goes to a key computed from the bytes
it writes. Two workers that do the same step write the same bytes to the same key, so the
worker that loses the lease has changed nothing that matters.
"""

import hashlib
from datetime import datetime

from gdelt import Stream

from worker.stamps import day, format_stamp

__all__ = ["display_key", "lake_keys", "raw_key"]

_FACTS = "lake/facts/gkg/v1/"
_DISPLAY = "lake/display/gkg/v1/"


def raw_key(stream: Stream, stamp: datetime, data: bytes) -> str:
    """Where a downloaded zip is kept: under the MD5 of the bytes that arrived, whether or not
    they are the bytes that were listed."""
    digest = hashlib.md5(data, usedforsecurity=False).hexdigest()
    return f"raw/gdelt/{stream.value}/dt={day(stamp)}/{digest}.zip"


def lake_keys(stream: Stream, stamp: datetime, facts: bytes, display: bytes) -> tuple[str, str]:
    """The keys of an interval's two lake files, facts first.

    Both carry one name under two prefixes, and the name holds one hash of both files. So the
    ledger's single `parquet_key` column, which stores the facts key, names the pair; and a
    change to either file gives both a new name.
    """
    both = hashlib.sha256(
        b"facts" + hashlib.sha256(facts).digest() + b"display" + hashlib.sha256(display).digest()
    ).hexdigest()[:32]
    name = f"dt={day(stamp)}/{stream.value}-{format_stamp(stamp)}-{both}.parquet"
    return _FACTS + name, _DISPLAY + name


def display_key(facts_key: str) -> str:
    """The display file that belongs to a facts file."""
    if not facts_key.startswith(_FACTS):
        raise ValueError(f"not a facts key: {facts_key!r}")
    return _DISPLAY + facts_key.removeprefix(_FACTS)
