"""The GKG 2.1 row contract.

A GKG file is one record per line, 27 tab-separated columns, no header and no quoting. The
contract a line must meet to become a row:

1. Exactly 27 columns.
2. A record ID of the form `YYYYMMDDHHMMSS-N` (English stream) or `YYYYMMDDHHMMSS-TN`
   (translated stream), with a real timestamp.
3. A `DATE` column that is a real `YYYYMMDDHHMMSS` timestamp.
4. Valid UTF-8 in every column the lean projection keeps.

A line that fails is quarantined with its reason and counted. Nothing is repaired: a record
that a stray line break cut in pieces is not stitched back together, a row with one column
too many is not trimmed.

Defects inside a kept column (a location entry with the wrong number of fields, a tone that
is not seven numbers, a title that is missing) do not fail the row. The damaged part is left
out and counted as an `Issue`.
"""

from enum import IntEnum, StrEnum

__all__ = ["COLUMN_COUNT", "KEPT_COLUMNS", "Column", "Issue", "Reason", "RowRejected"]

COLUMN_COUNT = 27


class Column(IntEnum):
    """The 27 columns of GKG 2.1, in file order, under the codebook's names."""

    GKGRECORDID = 0
    DATE = 1
    SOURCECOLLECTIONIDENTIFIER = 2
    SOURCECOMMONNAME = 3
    DOCUMENTIDENTIFIER = 4
    V1COUNTS = 5
    V21COUNTS = 6
    V1THEMES = 7
    V2ENHANCEDTHEMES = 8
    V1LOCATIONS = 9
    V2ENHANCEDLOCATIONS = 10
    V1PERSONS = 11
    V2ENHANCEDPERSONS = 12
    V1ORGANIZATIONS = 13
    V2ENHANCEDORGANIZATIONS = 14
    V15TONE = 15
    V21ENHANCEDDATES = 16
    V2GCAM = 17
    V21SHARINGIMAGE = 18
    V21RELATEDIMAGES = 19
    V21SOCIALIMAGEEMBEDS = 20
    V21SOCIALVIDEOEMBEDS = 21
    V21QUOTATIONS = 22
    V21ALLNAMES = 23
    V21AMOUNTS = 24
    V21TRANSLATIONINFO = 25
    V2EXTRASXML = 26


KEPT_COLUMNS = frozenset(
    {
        Column.GKGRECORDID,
        Column.DATE,
        Column.SOURCECOMMONNAME,
        Column.DOCUMENTIDENTIFIER,
        Column.V2ENHANCEDTHEMES,
        Column.V2ENHANCEDLOCATIONS,
        Column.V15TONE,
        Column.V21TRANSLATIONINFO,
        Column.V2EXTRASXML,  # only PAGE_TITLE and PAGE_PRECISEPUBTIMESTAMP are read from it
    }
)
"""The lean projection reads these columns. GCAM and the V1 columns are never decoded."""


class Reason(StrEnum):
    """Why a line was quarantined."""

    COLUMN_COUNT = "column_count"
    BAD_RECORD_ID = "bad_record_id"
    BAD_DATE = "bad_date"
    BAD_UTF8 = "bad_utf8"


class Issue(StrEnum):
    """A defect inside a row that was kept. The damaged part is left out, never repaired."""

    TITLE_MISSING = "title_missing"  # no PAGE_TITLE tag, or one that never closes
    TITLE_EMPTY = "title_empty"  # nothing left after cleaning
    TITLE_BAD_UTF8 = "title_bad_utf8"  # broken bytes became U+FFFD
    PUBLISHED_AT_INVALID = "published_at_invalid"
    URL_REJECTED = "url_rejected"  # the document identifier is not an absolute http(s) link
    LOCATION_MALFORMED = "location_malformed"  # counted per entry
    THEME_MALFORMED = "theme_malformed"  # counted per entry
    TONE_MALFORMED = "tone_malformed"
    SRCLC_UNKNOWN = "srclc_unknown"  # a source-language code the table does not hold
    TRANSLATION_INFO_MISSING = "translation_info_missing"  # a translated row without it
    TRANSLATION_INFO_MALFORMED = "translation_info_malformed"
    CENTROID_DEMOTED = "centroid_demoted"  # a blocklisted centroid was counted as country-level


class RowRejected(Exception):
    """Raised by `parse_line` for a line that fails the contract."""

    def __init__(self, reason: Reason) -> None:
        super().__init__(reason.value)
        self.reason = reason
