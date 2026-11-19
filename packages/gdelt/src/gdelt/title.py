"""Titles: decode the character references, sanitize, normalize to NFKC, hash.

GDELT writes every non-ASCII character of a page title as an upper-case hex reference
(`&#x6D4B;`) and leaves ASCII alone, a bare `&` included. In the three days of real files
read for this package (12-14 November 2026) every numeric reference was hex, and a handful
of titles also carried a named reference with its semicolon (`&AMP;`). On those files this
function and `html.unescape` gave the same title every time.

So `decode_entities` decodes numeric references and named references that end in a semicolon,
once, and touches nothing else. `R&D` stays `R&D`, and `&copy` without a semicolon stays text
instead of turning into a copyright sign.
"""

import hashlib
import html
import re
from html.entities import html5

from glcore.untrusted import sanitize

__all__ = ["TITLE_HASH_BYTES", "clean_title", "decode_entities", "title_hash"]

TITLE_HASH_BYTES = 8

_REFERENCE = re.compile(r"&(#[0-9]{1,10}|#[xX][0-9a-fA-F]{1,8}|[A-Za-z][A-Za-z0-9]{1,31});")
_NAMED = {name[:-1]: value for name, value in html5.items() if name.endswith(";")}


def _replace(match: re.Match[str]) -> str:
    reference = match.group(1)
    if reference[0] != "#":
        return _NAMED.get(reference, match.group(0))
    code = int(reference[2:], 16) if reference[1] in "xX" else int(reference[1:])
    if (
        0xA0 <= code < 0xD800
        or 0xE000 <= code < 0xFDD0
        or 0xFDF0 <= code <= 0xFFFD
        or (0x10000 <= code <= 0x10FFFF and code & 0xFFFE != 0xFFFE)
    ):
        return chr(code)
    # Controls, the C1 range browsers read as Windows-1252, surrogates, noncharacters and
    # out-of-range values: the HTML standard says what each becomes, and html.unescape knows.
    return html.unescape(match.group(0))


def decode_entities(text: str) -> str:
    """Decode HTML character references that end in a semicolon. One pass, never repeated."""
    if "&" not in text:
        return text
    return _REFERENCE.sub(_replace, text)


def clean_title(raw: str) -> str:
    """The title as stored and shown: references decoded, sanitized, NFKC. May be empty."""
    return sanitize(decode_entities(raw))


def title_hash(title: str) -> bytes:
    """The first 8 bytes of SHA-256 over the cleaned title's UTF-8 bytes.

    Exact copies of a headline share it. SHA-256 is used because Postgres, DuckDB and a
    browser can all recompute it without a library.
    """
    return hashlib.sha256(title.encode("utf-8")).digest()[:TITLE_HASH_BYTES]
