"""The object store: PUT and GET of whole objects by key.

The interface is the part of R2 the worker uses. `FolderStore` keeps the objects in a local
folder and `MemoryStore` in a dict, for tests; the R2 client arrives with the accounts. A key's
first segment is the bucket (`raw/…`, `lake/…`, `cdn/…`), as the design note writes its paths.

What the ledger relies on: a PUT is all or nothing, and a second PUT of the same bytes to the
same key changes nothing. `exists` is a HEAD: the publisher asks it before it PUTs an object
that a pass may already have written, because a PUT is a Class A operation and a HEAD is not.

`LoggingStore` wraps a store and appends one line per PUT to a file: the write log that the data
plane's measurement counts against the R2 write budget (docs/design/p1.md §6.6).
"""

import contextlib
import json
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Protocol

__all__ = ["FolderStore", "LoggingStore", "MemoryStore", "ObjectStore"]

_KEY = re.compile(r"[A-Za-z0-9._=-]+(/[A-Za-z0-9._=-]+)*")


class ObjectStore(Protocol):
    def put(self, key: str, data: bytes) -> None:
        """Store `data` under `key`, replacing what was there."""
        ...

    def get(self, key: str) -> bytes | None:
        """The object under `key`, or None if there is none."""
        ...

    def exists(self, key: str) -> bool:
        """True if there is an object under `key`."""
        ...


class FolderStore:
    """Objects as files under one folder."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def _path(self, key: str) -> Path:
        if _KEY.fullmatch(key) is None or any(part in (".", "..") for part in key.split("/")):
            raise ValueError(f"not an object key: {key!r}")
        return self._root / key

    def put(self, key: str, data: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Written beside the object and renamed over it, so a reader sees the old object or
        # the new one and never a part of one.
        handle, partial = tempfile.mkstemp(dir=path.parent, prefix=".put-")
        try:
            with os.fdopen(handle, "wb") as out:
                out.write(data)
                out.flush()
                os.fsync(out.fileno())
            os.replace(partial, path)
            # The rename lives in the folder, so the folder is synced as well.
            folder = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(folder)
            finally:
                os.close(folder)
        except BaseException:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(partial)
            raise

    def get(self, key: str) -> bytes | None:
        path = self._path(key)
        try:
            return path.read_bytes()
        except (FileNotFoundError, IsADirectoryError, NotADirectoryError):
            return None

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()


class MemoryStore:
    """Objects in a dict. For tests."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put(self, key: str, data: bytes) -> None:
        if _KEY.fullmatch(key) is None:
            raise ValueError(f"not an object key: {key!r}")
        self.objects[key] = data

    def get(self, key: str) -> bytes | None:
        return self.objects.get(key)

    def exists(self, key: str) -> bool:
        return key in self.objects


class LoggingStore:
    """A store that also appends one JSON line per PUT to `log`: the time (UTC), the key, the
    size and the process. Keys hold hashes, stamps and streams, never a title. Several
    processes may append to one log: each line is written with a single call."""

    def __init__(self, inner: ObjectStore, log: Path) -> None:
        self._inner = inner
        self._log = log

    def put(self, key: str, data: bytes) -> None:
        self._inner.put(key, data)
        line = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "key": key,
            "bytes": len(data),
            "pid": os.getpid(),
        }
        handle = os.open(self._log, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
        try:
            os.write(handle, (json.dumps(line, sort_keys=True) + "\n").encode())
        finally:
            os.close(handle)

    def get(self, key: str) -> bytes | None:
        return self._inner.get(key)

    def exists(self, key: str) -> bool:
        return self._inner.exists(key)
