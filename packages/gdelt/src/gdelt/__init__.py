"""GDELT GKG 2.1: the 27-column contract, the lean parser, the language table.

    from gdelt import parse_gkg

    result = parse_gkg(unzipped_bytes)
    result.rows          # list[LeanRow]
    result.quarantined   # lines that failed the contract, byte for byte
    result.stats         # counts, issues inside kept rows, unknown language codes

Data: the GDELT Project (https://www.gdeltproject.org/).
"""

from gdelt.contract import COLUMN_COUNT, KEPT_COLUMNS, Column, Issue, Reason, RowRejected
from gdelt.files import find_gkg_files, read_gkg_bytes
from gdelt.jsonio import result_to_json, row_to_json
from gdelt.lang import ENGLISH, LANG_TABLE_VERSION, LANGS, Lang, from_srclc, srclc_of
from gdelt.location import (
    BLOCKLISTED_CENTROIDS,
    Location,
    PrimaryLocation,
    parse_locations,
    select_primary,
)
from gdelt.parse import (
    LeanRow,
    ParseResult,
    ParseStats,
    Quarantined,
    Stream,
    Tone,
    parse_gkg,
    parse_line,
)
from gdelt.title import TITLE_HASH_BYTES, clean_title, decode_entities, title_hash
from gdelt.urlcanon import MAX_URL_CHARS, TRACKING_PARAMETERS, canon_url

__all__ = [
    "BLOCKLISTED_CENTROIDS",
    "COLUMN_COUNT",
    "ENGLISH",
    "KEPT_COLUMNS",
    "LANGS",
    "LANG_TABLE_VERSION",
    "MAX_URL_CHARS",
    "TITLE_HASH_BYTES",
    "TRACKING_PARAMETERS",
    "Column",
    "Issue",
    "Lang",
    "LeanRow",
    "Location",
    "ParseResult",
    "ParseStats",
    "PrimaryLocation",
    "Quarantined",
    "Reason",
    "RowRejected",
    "Stream",
    "Tone",
    "canon_url",
    "clean_title",
    "decode_entities",
    "find_gkg_files",
    "from_srclc",
    "parse_gkg",
    "parse_line",
    "parse_locations",
    "read_gkg_bytes",
    "result_to_json",
    "row_to_json",
    "select_primary",
    "srclc_of",
    "title_hash",
]
