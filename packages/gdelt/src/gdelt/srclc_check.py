"""The `srclc` check: every source-language code in a set of GKG files is in `gdelt.lang`.

    python -m gdelt.srclc_check [--require-days N] PATH [PATH ...]

A path is a GKG file (`.csv` or `.csv.zip`) or a folder of them. The exit code is 0 only if
at least one row was read, no unknown code was found and at least N different days were
covered. Day counts come from the 14-digit stamp that starts each of GDELT's file names.

The plan's gate is a week of data with 0 unknown codes: `--require-days 7`. The real files
are never committed, so this runs where they are kept.
"""

import argparse
import json
import re
import sys
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from gdelt.contract import COLUMN_COUNT
from gdelt.files import find_gkg_files, read_gkg_bytes
from gdelt.lang import from_srclc, srclc_of

__all__ = ["SrclcReport", "check_paths", "main"]

_STAMPED_NAME = re.compile(r"(\d{8})\d{6}\.")


@dataclass(frozen=True, slots=True)
class SrclcReport:
    files: int
    rows: int  # lines with 27 columns
    malformed_lines: int  # non-empty lines with any other column count; not read
    days: tuple[str, ...]  # YYYYMMDD, from the file names
    codes: dict[str, int]  # every code seen, with its row count
    unknown: dict[str, int]  # the codes that are not in the language table
    require_days: int

    @property
    def ok(self) -> bool:
        return self.rows > 0 and not self.unknown and len(self.days) >= self.require_days

    def to_json(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "files": self.files,
            "rows": self.rows,
            "malformed_lines": self.malformed_lines,
            "days": list(self.days),
            "require_days": self.require_days,
            "distinct_codes": len(self.codes),
            "unknown": self.unknown,
            "codes": self.codes,
        }


def check_paths(paths: Iterable[Path], *, require_days: int = 0) -> SrclcReport:
    """Read the TranslationInfo column of every row under `paths` and tally the codes."""
    codes: Counter[str] = Counter()
    days: set[str] = set()
    files = rows = malformed = 0
    for path in find_gkg_files(paths):
        files += 1
        stamped = _STAMPED_NAME.match(path.name)
        if stamped:
            days.add(stamped.group(1))
        for raw in read_gkg_bytes(path).split(b"\n"):
            if not raw:
                continue
            columns = raw.split(b"\t")
            if len(columns) != COLUMN_COUNT:
                malformed += 1
                continue
            rows += 1
            info = columns[25]
            if info:
                code = srclc_of(info.decode("utf-8", "replace"))
                if code is not None:
                    codes[code] += 1
    ordered = dict(sorted(codes.items(), key=lambda item: (-item[1], item[0])))
    unknown = {code: count for code, count in ordered.items() if from_srclc(code) is None}
    return SrclcReport(files, rows, malformed, tuple(sorted(days)), ordered, unknown, require_days)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m gdelt.srclc_check", description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path, help="GKG files or folders of them")
    parser.add_argument("--require-days", type=int, default=0, metavar="N")
    args = parser.parse_args(argv)
    report = check_paths(args.paths, require_days=args.require_days)
    print(json.dumps(report.to_json(), ensure_ascii=False, indent=2))
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
