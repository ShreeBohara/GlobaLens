"""Untrusted text: sanitizer v0.

Titles, outlet names and place names come from other people's web pages. This module is the one
place that cleans such text before anything stores it, renders it or (from Phase 2) puts it in a
prompt. Version 0 is the part Phase 1 needs: one function, `sanitize`.

What `sanitize` does, in order:

1. Line breaks, tabs and the other space-like controls become a space.
2. Characters that are invisible and can mislead a reader or a model are removed:
   bidi embeddings, overrides and isolates (U+202A-202E, U+2066-2069); zero-width space, word
   joiner and BOM (U+200B, U+2060, U+FEFF); the soft hyphen and the other invisible format
   characters; Unicode tag characters (U+E0000-E007F); the remaining C0 and C1 controls;
   noncharacters and lone surrogates.
3. The text is normalized to NFKC.
4. Runs of spaces collapse to one, and the ends are trimmed.
5. The result is cut to `max_chars` code points, without splitting a character from its
   combining marks or cutting inside a sequence joined by ZWJ.

What it keeps on purpose (`KEPT_FORMAT_CHARS`): the zero-width joiner and non-joiner, which
Persian and Indic scripts need to shape words; the three direction marks (LRM, RLM, ALM), which
only tidy punctuation at the edge of mixed-direction text; and the visible Arabic, Syriac and
Kaithi number and verse signs, which are format characters in name only.

What it does not do: escape markup. `<b>` stays `<b>`, because text is rendered as a text node
and never as HTML. Removing angle brackets here would change honest headlines.

The output is always NFKC, at most `max_chars` long, and unchanged by a second pass.
"""

import re
import unicodedata

__all__ = ["KEPT_FORMAT_CHARS", "MAX_CHARS", "SANITIZER_VERSION", "sanitize"]

SANITIZER_VERSION = 0
"""Bumped whenever `sanitize` can return a different string for the same input. Anything keyed
on sanitized text (a title hash, a memoized translation) is only comparable within one version."""

MAX_CHARS = 300
"""Default cap in code points (plan section 8: "cap at ~300 characters")."""

KEPT_FORMAT_CHARS = frozenset(
    "\u200c\u200d"  # ZWNJ, ZWJ: shaping
    "\u200e\u200f\u061c"  # LRM, RLM, ALM: direction marks
    "\u0600\u0601\u0602\u0603\u0604\u0605"  # visible Arabic number signs
    "\u06dd\u070f\u0890\u0891\u08e2"  # visible Arabic and Syriac signs
    "\U000110bd\U000110cd"  # visible Kaithi number signs
    + "".join(chr(cp) for cp in range(0x13430, 0x13440))  # Egyptian hieroglyph layout controls
)
"""Every Unicode format character (category Cf) that `sanitize` leaves in place."""

_SPACE_LIKE = re.compile("[\t\n\x0b\x0c\r\x1c-\x1f\x85\u2028\u2029]")

_REMOVED = re.compile(
    "["
    "\x00-\x08\x0e-\x1b\x7f-\x84\x86-\x9f"  # C0 and C1 controls that are not space-like
    "\u00ad"  # soft hyphen
    "\u180e"  # Mongolian vowel separator
    "\u200b"  # zero-width space
    "\u202a-\u202e"  # bidi embeddings and overrides
    "\u2060-\u2064"  # word joiner, invisible operators
    "\u2066-\u206f"  # bidi isolates, deprecated format characters
    "\ufeff"  # BOM, zero-width no-break space
    "\ufff9-\ufffb"  # interlinear annotation
    "\U0001bca0-\U0001bca3"  # shorthand format controls
    "\U0001d173-\U0001d17a"  # musical format controls
    "\U000e0000-\U000e007f"  # tag characters
    "\ud800-\udfff"  # lone surrogates
    "\ufdd0-\ufdef"  # noncharacters
    + "".join(
        f"{chr(plane * 0x10000 + 0xFFFE)}{chr(plane * 0x10000 + 0xFFFF)}" for plane in range(17)
    )
    + "]"
)

_SPACE_RUN = re.compile(" {2,}")

_JOINERS = "\u200c\u200d"
_MAX_BACK_OFF = 16


def _starts_mid_cluster(ch: str) -> bool:
    """True when `ch` belongs with the character before it: a combining mark, a variation
    selector (both category M) or a joiner."""
    return ch in _JOINERS or unicodedata.category(ch)[0] == "M"


def _cut(text: str, max_chars: int) -> str:
    """Cut to at most `max_chars` code points at a place that splits no cluster, looking back at
    most `_MAX_BACK_OFF` characters for one; a run of marks longer than that is cut where it is."""
    lowest = max(max_chars - _MAX_BACK_OFF, 0)
    end = max_chars
    while end > lowest and (_starts_mid_cluster(text[end]) or text[end - 1] == "\u200d"):
        end -= 1
    if end == lowest:
        end = max_chars  # one cluster fills the whole window: cut it rather than return nothing
    return text[:end].rstrip(" ")


def sanitize(text: str, *, max_chars: int = MAX_CHARS) -> str:
    """Clean a piece of third-party text. See the module docstring for the rules."""
    if max_chars < 1:
        raise ValueError("max_chars must be at least 1")
    if _SPACE_LIKE.search(text):
        text = _SPACE_LIKE.sub(" ", text)
    if _REMOVED.search(text):
        text = _REMOVED.sub("", text)
    if not text.isascii() and not unicodedata.is_normalized("NFKC", text):
        # NFKC maps no character to one this function removes (a test checks every code point),
        # so the two steps above need no second pass.
        text = unicodedata.normalize("NFKC", text)
    if "  " in text:
        text = _SPACE_RUN.sub(" ", text)
    text = text.strip(" ")
    if len(text) > max_chars:
        text = _cut(text, max_chars)
    return text
