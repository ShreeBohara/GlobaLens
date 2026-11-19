"""The GKG 2.1 parser: bytes in, lean rows out, bad lines quarantined.

`parse_gkg` takes the bytes of one unzipped GKG file. `parse_line` takes one line. Both apply
the contract of `gdelt.contract` and return the lean projection: record ID, date, outlet,
URL, locations, tone, themes, translation info, and from the extras column the page title
and the precise publication time. GCAM, the V1 columns and everything else are dropped
without being decoded.

Every string in a `LeanRow` is either matched against a strict pattern (IDs, codes, theme
names) or has been through `glcore.untrusted.sanitize` (title, outlet, place names,
translation info). The canonical URL contains no whitespace, control or invisible character.
"""

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from functools import lru_cache
from typing import NamedTuple

from glcore.untrusted import sanitize

from gdelt.contract import COLUMN_COUNT, Issue, Reason, RowRejected
from gdelt.lang import ENGLISH, Lang, from_srclc, srclc_of
from gdelt.location import Location, PrimaryLocation, parse_locations, select_primary
from gdelt.title import clean_title, title_hash
from gdelt.urlcanon import canon_url

__all__ = [
    "LeanRow",
    "ParseResult",
    "ParseStats",
    "Quarantined",
    "Stream",
    "Tone",
    "parse_gkg",
    "parse_line",
]


class Stream(StrEnum):
    """Which of GDELT's two GKG streams a row came from. The values match `ingest.stream`."""

    ENGLISH = "english"
    TRANSLATED = "translated"


class Tone(NamedTuple):
    """The seven numbers of the tone column, as GDELT gives them."""

    tone: float
    positive: float
    negative: float
    polarity: float
    activity_density: float
    self_group_density: float
    word_count: float


@dataclass(frozen=True, slots=True)
class LeanRow:
    """One article: the lean projection of a GKG row."""

    record_id: str  # GKGRECORDID as given
    stream: Stream
    seq: int  # the record number inside its 15-minute interval
    stamp: datetime  # the DATE column, UTC
    outlet: str  # SourceCommonName: the outlet's domain as GDELT gives it
    url: str | None  # canonical; None when the document identifier is not an http(s) link
    title: str | None  # cleaned; None when missing or empty
    title_hash: bytes | None
    published_at: datetime | None  # PAGE_PRECISEPUBTIMESTAMP, UTC
    srclc: str | None  # the source-language code as given; None when there is none
    lang: Lang | None  # None when the language is not known
    translation_info: str  # the TranslationInfo column, sanitized
    tone: Tone | None
    themes: tuple[str, ...]  # V2 theme names, unique, in file order
    locations: tuple[Location, ...]  # every mention, in file order
    primary: PrimaryLocation | None


class Quarantined(NamedTuple):
    """A line that failed the contract, kept byte for byte."""

    line_no: int  # 1-based
    reason: Reason
    raw: bytes


def _counter() -> Counter[str]:
    return Counter()


@dataclass(slots=True)
class ParseStats:
    lines: int = 0  # physical lines, blank ones included
    rows: int = 0  # lines that met the contract
    blank_lines: int = 0  # empty lines; not rows, not quarantined
    quarantined: Counter[str] = field(default_factory=_counter)  # by Reason
    issues: Counter[str] = field(default_factory=_counter)  # by Issue
    unknown_srclc: Counter[str] = field(default_factory=_counter)  # by code

    @property
    def malformed_share(self) -> float:
        """Quarantined lines as a share of the non-blank lines."""
        candidates = self.lines - self.blank_lines
        return sum(self.quarantined.values()) / candidates if candidates else 0.0

    def add(self, other: "ParseStats") -> None:
        """Fold another file's counts into this one."""
        self.lines += other.lines
        self.rows += other.rows
        self.blank_lines += other.blank_lines
        self.quarantined.update(other.quarantined)
        self.issues.update(other.issues)
        self.unknown_srclc.update(other.unknown_srclc)


class ParseResult(NamedTuple):
    rows: list[LeanRow]
    quarantined: list[Quarantined]
    stats: ParseStats


_RECORD_ID = re.compile(rb"(\d{14})-(T?)(\d{1,9})")
_THEME = re.compile(r"(?:^|;)([A-Za-z0-9_]+),\d+(?=;|$)")
_NUMBER = r"-?\d+(?:\.\d+)?"
_TONE = re.compile(",".join([f"({_NUMBER})"] * 7))

_TITLE_OPEN = b"<PAGE_TITLE>"
_TITLE_CLOSE = b"</PAGE_TITLE>"
_PUBLISHED_OPEN = b"<PAGE_PRECISEPUBTIMESTAMP>"
_PUBLISHED_CLOSE = b"</PAGE_PRECISEPUBTIMESTAMP>"


@lru_cache(maxsize=8192)
def _timestamp(text: bytes) -> datetime | None:
    """A `YYYYMMDDHHMMSS` timestamp in UTC, or None if `text` is not one."""
    if len(text) != 14 or not text.isdigit():
        return None
    try:
        return datetime(
            int(text[0:4]),
            int(text[4:6]),
            int(text[6:8]),
            int(text[8:10]),
            int(text[10:12]),
            int(text[12:14]),
            tzinfo=UTC,
        )
    except ValueError:
        return None


def _themes(column: str, issues: Counter[str] | None) -> tuple[str, ...]:
    if not column:
        return ()
    names: list[str] = _THEME.findall(column)
    if issues is not None and len(names) != column.count(";") + (not column.endswith(";")):
        malformed = sum(1 for entry in column.split(";") if entry) - len(names)
        if malformed:
            issues[Issue.THEME_MALFORMED] += malformed
    return tuple(dict.fromkeys(names))


def parse_line(raw: bytes, issues: Counter[str] | None = None) -> LeanRow:
    """Parse one line of a GKG file. Raises `RowRejected` if it fails the contract.

    Defects inside a kept column are tallied in `issues` (keyed by `Issue`) when it is given.
    """
    columns = raw.split(b"\t")
    if len(columns) != COLUMN_COUNT:
        raise RowRejected(Reason.COLUMN_COUNT)

    identifier = _RECORD_ID.fullmatch(columns[0])
    if identifier is None or _timestamp(identifier.group(1)) is None:
        raise RowRejected(Reason.BAD_RECORD_ID)
    stamp = _timestamp(columns[1])
    if stamp is None:
        raise RowRejected(Reason.BAD_DATE)
    try:
        outlet = columns[3].decode("utf-8")
        identifier_text = columns[4].decode("utf-8")
        themes_text = columns[8].decode("utf-8")
        locations_text = columns[10].decode("utf-8")
        tone_text = columns[15].decode("utf-8")
        translation_info = columns[25].decode("utf-8")
    except UnicodeDecodeError:
        raise RowRejected(Reason.BAD_UTF8) from None

    stream = Stream.TRANSLATED if identifier.group(2) else Stream.ENGLISH

    url = canon_url(identifier_text)
    if url is None and issues is not None:
        issues[Issue.URL_REJECTED] += 1

    # Language.
    srclc: str | None = None
    lang: Lang | None = None
    if translation_info:
        translation_info = sanitize(translation_info)
        srclc = srclc_of(translation_info)
        if srclc is None:
            if issues is not None:
                issues[Issue.TRANSLATION_INFO_MALFORMED] += 1
        else:
            lang = from_srclc(srclc)
            if lang is None and issues is not None:
                issues[Issue.SRCLC_UNKNOWN] += 1
    elif stream is Stream.ENGLISH:
        lang = ENGLISH
    elif issues is not None:
        issues[Issue.TRANSLATION_INFO_MISSING] += 1

    # Tone.
    tone: Tone | None = None
    tone_match = _TONE.fullmatch(tone_text)
    if tone_match is not None:
        tone = Tone(*map(float, tone_match.groups()))
    elif issues is not None:
        issues[Issue.TONE_MALFORMED] += 1

    # Locations.
    locations, malformed = parse_locations(locations_text)
    if malformed and issues is not None:
        issues[Issue.LOCATION_MALFORMED] += malformed
    primary = select_primary(locations) if locations else None
    if primary is not None and primary.demoted and issues is not None:
        issues[Issue.CENTROID_DEMOTED] += 1

    # Extras: the title and the precise publication time. Nothing else in it is read.
    extras = columns[26]
    title: str | None = None
    start = extras.find(_TITLE_OPEN)
    end = extras.find(_TITLE_CLOSE, start + 12) if start >= 0 else -1
    if end < 0:
        if issues is not None:
            issues[Issue.TITLE_MISSING] += 1
    else:
        title_bytes = extras[start + 12 : end]
        try:
            title_text = title_bytes.decode("utf-8")
        except UnicodeDecodeError:
            title_text = title_bytes.decode("utf-8", "replace")
            if issues is not None:
                issues[Issue.TITLE_BAD_UTF8] += 1
        title = clean_title(title_text) or None
        if title is None and issues is not None:
            issues[Issue.TITLE_EMPTY] += 1

    published_at: datetime | None = None
    start = extras.find(_PUBLISHED_OPEN)
    if start >= 0:
        end = extras.find(_PUBLISHED_CLOSE, start + 26)
        if end >= 0:
            published_at = _timestamp(extras[start + 26 : end])
        if published_at is None and issues is not None:
            issues[Issue.PUBLISHED_AT_INVALID] += 1

    return LeanRow(
        record_id=columns[0].decode("ascii"),
        stream=stream,
        seq=int(identifier.group(3)),
        stamp=stamp,
        outlet=sanitize(outlet),
        url=url,
        title=title,
        title_hash=title_hash(title) if title is not None else None,
        published_at=published_at,
        srclc=srclc,
        lang=lang,
        translation_info=translation_info,
        tone=tone,
        themes=_themes(themes_text, issues),
        locations=locations,
        primary=primary,
    )


def parse_gkg(data: bytes) -> ParseResult:
    """Parse the bytes of one unzipped GKG file.

    Lines end in a line feed. An empty line is counted and skipped. A line that fails the
    contract goes to the quarantine list with its line number, its reason and its bytes.
    """
    stats = ParseStats()
    rows: list[LeanRow] = []
    quarantined: list[Quarantined] = []
    lines = data.split(b"\n")
    if lines[-1] == b"":
        lines.pop()  # the file's final line feed, or an empty file
    issues = stats.issues
    for line_no, raw in enumerate(lines, 1):
        if not raw:
            stats.blank_lines += 1
            continue
        try:
            row = parse_line(raw, issues)
        except RowRejected as rejected:
            quarantined.append(Quarantined(line_no, rejected.reason, raw))
            stats.quarantined[rejected.reason] += 1
            continue
        rows.append(row)
        if row.lang is None and row.srclc is not None:
            stats.unknown_srclc[row.srclc] += 1
    stats.lines = len(lines)
    stats.rows = len(rows)
    return ParseResult(rows, quarantined, stats)
