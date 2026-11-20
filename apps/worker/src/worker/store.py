"""The object store: PUT and GET of whole objects by key.

The interface is the part of R2 the worker uses. `FolderStore` keeps the objects in a local
folder and `MemoryStore` in a dict, for tests; the R2 client arrives with the accounts. A key's
first segment is the bucket (`raw/…`, `lake/…`), as the design note writes its paths.

What the ledger relies on: a PUT is all or nothing, and a second PUT of the same bytes to the
same key changes nothing.
"""

import contextlib
import os
import re
import tempfile
from pathlib import Path
from typing import Protocol

__all__ = ["FolderStore", "MemoryStore", "ObjectStore"]

_KEY = re.compile(r"[A-Za-z0-9._=-]+(/[A-Za-z0-9._=-]+)*")


class ObjectStore(Protocol):
    def put(self, key: str, data: bytes) -> None:
        """Store `data` under `key`, replacing what was there."""
        ...

    def get(self, key: str) -> bytes | None:
        """The object under `key`, or None if there is none."""
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
