"""The folder object store: PUT and GET by key, whole objects only."""

import json
import os
from pathlib import Path

import pytest
from worker.store import FolderStore, LoggingStore, MemoryStore


def test_an_object_comes_back_as_it_was_put(tmp_path: Path) -> None:
    store = FolderStore(tmp_path)
    store.put("raw/gdelt/english/dt=2026-11-20/abc.zip", b"\x00\x01zip")
    assert store.get("raw/gdelt/english/dt=2026-11-20/abc.zip") == b"\x00\x01zip"
    assert (tmp_path / "raw/gdelt/english/dt=2026-11-20/abc.zip").read_bytes() == b"\x00\x01zip"


def test_a_key_that_was_never_put_is_none(tmp_path: Path) -> None:
    store = FolderStore(tmp_path)
    assert store.get("raw/none.zip") is None
    store.put("raw/a/b.zip", b"x")
    assert store.get("raw/a") is None  # a folder is not an object
    assert store.get("raw/a/c.zip") is None


def test_a_second_put_to_the_same_key_replaces_the_object(tmp_path: Path) -> None:
    store = FolderStore(tmp_path)
    store.put("lake/a.parquet", b"one")
    store.put("lake/a.parquet", b"one")
    assert store.get("lake/a.parquet") == b"one"
    store.put("lake/a.parquet", b"two")
    assert store.get("lake/a.parquet") == b"two"


def test_a_put_leaves_nothing_but_the_object(tmp_path: Path) -> None:
    store = FolderStore(tmp_path)
    store.put("lake/facts/x.parquet", b"data")
    store.put("lake/facts/x.parquet", b"data")
    files = sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*"))
    assert files == ["lake", "lake/facts", "lake/facts/x.parquet"]


def test_the_root_folder_is_created_when_it_is_missing(tmp_path: Path) -> None:
    store = FolderStore(tmp_path / "new" / "store")
    store.put("a.bin", b"1")
    assert store.get("a.bin") == b"1"


@pytest.mark.parametrize(
    "key",
    [
        "",
        "/etc/hosts",
        "../outside",
        "raw/../../outside",
        "raw/./a",
        "raw//a",
        "raw/a/",
        "raw\\a",
        "raw/a b",
        "raw/a\n",
        "raw/.",
        "..",
    ],
)
def test_a_key_that_is_not_a_plain_path_is_refused(tmp_path: Path, key: str) -> None:
    store = FolderStore(tmp_path / "store")
    with pytest.raises(ValueError):
        store.put(key, b"x")
    with pytest.raises(ValueError):
        store.get(key)
    assert not (tmp_path / "outside").exists()


# --- exists, and the write log -------------------------------------------------------------


def test_exists_says_whether_an_object_is_there(tmp_path: Path) -> None:
    for store in (FolderStore(tmp_path), MemoryStore()):
        assert not store.exists("cdn/live/a.arrow")
        store.put("cdn/live/a.arrow", b"x")
        assert store.exists("cdn/live/a.arrow")
        assert not store.exists("cdn/live")  # a folder is not an object
        assert not store.exists("cdn/live/b.arrow")


def test_exists_refuses_a_key_that_is_not_a_plain_path(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        FolderStore(tmp_path).exists("../outside")


def test_the_write_log_has_one_line_per_put_and_none_per_get(tmp_path: Path) -> None:
    log = tmp_path / "writes.jsonl"
    inner = MemoryStore()
    store = LoggingStore(inner, log)
    store.put("cdn/live/dt=2026-11-20/shards/abc.arrow", b"12345")
    store.put("cdn/now.json", b"{}")
    store.put("cdn/now.json", b"{}")
    assert store.get("cdn/now.json") == b"{}"
    assert store.exists("cdn/now.json") and not store.exists("cdn/x")
    assert inner.objects["cdn/now.json"] == b"{}"
    lines = [json.loads(line) for line in log.read_text().splitlines()]
    assert [(line["key"], line["bytes"]) for line in lines] == [
        ("cdn/live/dt=2026-11-20/shards/abc.arrow", 5),
        ("cdn/now.json", 2),
        ("cdn/now.json", 2),
    ]
    assert all(line["pid"] == os.getpid() and line["ts"].endswith("Z") for line in lines)


def test_a_put_that_fails_is_not_logged(tmp_path: Path) -> None:
    log = tmp_path / "writes.jsonl"
    store = LoggingStore(FolderStore(tmp_path / "store"), log)
    with pytest.raises(ValueError):
        store.put("../outside", b"x")
    assert not log.exists() or log.read_text() == ""
