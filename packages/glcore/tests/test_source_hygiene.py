"""No source file hides a character.

A bidi control, a zero-width character or a no-break space typed straight into a source file
cannot be seen in review. The sanitizer and its tests are full of such characters, so every one
of them is written as an escape sequence, and this test fails on a literal one.
"""

import unicodedata
from pathlib import Path

PACKAGE = Path(__file__).parent.parent
CHECKED_SUFFIXES = {".py", ".json", ".toml", ".md"}


def hidden_characters(text: str) -> list[str]:
    found: list[str] = []
    for line_no, line in enumerate(text.split("\n"), 1):
        for ch in line:
            code = ord(ch)
            if 0x20 <= code < 0x7F:
                continue
            category = unicodedata.category(ch)
            if (
                category in ("Cc", "Cf", "Cs", "Co", "Zl", "Zp", "Zs")
                or 0xFE00 <= code <= 0xFE0F  # variation selectors
                or 0xFDD0 <= code <= 0xFDEF  # noncharacters
                or code & 0xFFFE == 0xFFFE
            ):
                found.append(f"line {line_no}: U+{code:04X}")
    return found


def checked_files(package: Path) -> list[Path]:
    return sorted(
        path
        for folder in ("src", "tests")
        for path in (package / folder).rglob("*")
        if path.is_file() and path.suffix in CHECKED_SUFFIXES
    )


def test_the_check_sees_what_it_should() -> None:
    assert hidden_characters("plain ASCII, and visible text: caf" + chr(0xE9)) == []
    assert hidden_characters("a" + chr(0x202E) + "b\n" + chr(0xA0)) == [
        "line 1: U+202E",
        "line 2: U+00A0",
    ]
    assert hidden_characters("tab\there") == ["line 1: U+0009"]


def test_no_source_file_holds_a_hidden_character() -> None:
    files = checked_files(PACKAGE)
    assert len(files) >= 4
    for path in files:
        found = hidden_characters(path.read_text(encoding="utf-8"))
        assert not found, f"{path.relative_to(PACKAGE)}: write these as escapes: {found[:5]}"
