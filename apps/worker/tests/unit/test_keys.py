"""Object keys are derived from content, so a repeated PUT lands on the same key."""

import hashlib
import re
from datetime import UTC, datetime

import pytest
from gdelt import Stream
from worker.ledger import keys

STAMP = datetime(2026, 11, 20, 1, 30, tzinfo=UTC)
VALID_KEY = re.compile(r"[A-Za-z0-9._=-]+(/[A-Za-z0-9._=-]+)*")


def test_a_raw_zip_is_stored_under_its_own_md5() -> None:
    key = keys.raw_key(Stream.ENGLISH, STAMP, b"abc")
    assert key == "raw/gdelt/english/dt=2026-11-20/900150983cd24fb0d6963f7d28e17f72.zip"
    assert keys.raw_key(Stream.ENGLISH, STAMP, b"abc") == key
    assert keys.raw_key(Stream.ENGLISH, STAMP, b"abd") != key
    assert keys.raw_key(Stream.TRANSLATED, STAMP, b"abc").startswith("raw/gdelt/translated/")


def test_the_two_lake_files_share_one_name_under_two_prefixes() -> None:
    facts_key, display_key = keys.lake_keys(Stream.TRANSLATED, STAMP, b"facts", b"display")
    name = facts_key.removeprefix("lake/facts/gkg/v1/")
    assert facts_key == "lake/facts/gkg/v1/" + name
    assert display_key == "lake/display/gkg/v1/" + name
    assert re.fullmatch(r"dt=2026-11-20/translated-20261120013000-[0-9a-f]{32}\.parquet", name)


def test_the_name_is_a_hash_of_both_files() -> None:
    inner = hashlib.sha256(
        b"facts" + hashlib.sha256(b"F").digest() + b"display" + hashlib.sha256(b"D").digest()
    ).hexdigest()[:32]
    facts_key, _ = keys.lake_keys(Stream.ENGLISH, STAMP, b"F", b"D")
    assert facts_key == f"lake/facts/gkg/v1/dt=2026-11-20/english-20261120013000-{inner}.parquet"


def test_changing_either_file_changes_both_keys() -> None:
    base = keys.lake_keys(Stream.ENGLISH, STAMP, b"facts", b"display")
    other_facts = keys.lake_keys(Stream.ENGLISH, STAMP, b"facts!", b"display")
    other_display = keys.lake_keys(Stream.ENGLISH, STAMP, b"facts", b"display!")
    swapped = keys.lake_keys(Stream.ENGLISH, STAMP, b"display", b"facts")
    for changed in (other_facts, other_display, swapped):
        assert changed[0] != base[0]
        assert changed[1] != base[1]
    assert keys.lake_keys(Stream.ENGLISH, STAMP, b"facts", b"display") == base


def test_the_display_key_is_derived_from_the_facts_key() -> None:
    facts_key, display_key = keys.lake_keys(Stream.ENGLISH, STAMP, b"facts", b"display")
    assert keys.display_key(facts_key) == display_key


@pytest.mark.parametrize(
    "key",
    [
        "",
        "lake/display/gkg/v1/dt=2026-11-20/english-20261120013000-00.parquet",
        "raw/gdelt/english/dt=2026-11-20/900150983cd24fb0d6963f7d28e17f72.zip",
        "x/lake/facts/gkg/v1/a.parquet",
    ],
)
def test_only_a_facts_key_has_a_display_key(key: str) -> None:
    with pytest.raises(ValueError):
        keys.display_key(key)


def test_every_key_is_a_plain_path() -> None:
    made = [
        keys.raw_key(Stream.ENGLISH, STAMP, b"abc"),
        *keys.lake_keys(Stream.TRANSLATED, STAMP, b"facts", b"display"),
    ]
    for key in made:
        assert VALID_KEY.fullmatch(key), key
