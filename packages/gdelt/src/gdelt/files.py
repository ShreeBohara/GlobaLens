"""Reading GKG files from disk: a `.csv`, or the `.csv.zip` GDELT publishes."""

import re
import zipfile
from collections.abc import Iterable, Iterator
from pathlib import Path

__all__ = ["find_gkg_files", "read_gkg_bytes"]

_GKG_NAME = re.compile(r"\.gkg\.csv(\.zip)?$", re.IGNORECASE)


def read_gkg_bytes(path: Path) -> bytes:
    """The unzipped bytes of one GKG file. A zip must hold exactly one member."""
    if path.suffix.lower() != ".zip":
        return path.read_bytes()
    with zipfile.ZipFile(path) as archive:
        members = archive.namelist()
        if len(members) != 1:
            raise ValueError(f"{path.name}: expected one file in the zip, found {len(members)}")
        return archive.read(members[0])


def find_gkg_files(paths: Iterable[Path]) -> Iterator[Path]:
    """Files are yielded as given. A folder yields the `*.gkg.csv` and `*.gkg.csv.zip` files
    under it, sorted by name."""
    for path in paths:
        if path.is_dir():
            yield from sorted(
                p for p in path.rglob("*") if p.is_file() and _GKG_NAME.search(p.name)
            )
        else:
            yield path
