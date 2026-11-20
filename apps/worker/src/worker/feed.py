"""GDELT's listing files, and the HTTP that reads them and the zips.

`lastupdate.txt` and `lastupdate-translation.txt` each hold three lines, one per file type of
the newest 15-minute batch. The master lists hold the same lines for every batch ever
published. A line is `<size> <md5> <url>`; only the GKG line of the asked-for stream is read.

Nothing here follows a URL that a listing gives: a file's URL is built from its stream and
stamp (`worker.stamps`), `http_get` refuses any address that is not GDELT's own HTTPS folder,
and it follows no redirect, so an answer can only come from that folder. HTTP is the standard
library's.

Data: the GDELT Project (https://www.gdeltproject.org/).
"""

import http.client
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime

from gdelt import Stream

from worker.stamps import parse_stamp

__all__ = [
    "LASTUPDATE_URL",
    "MASTERLIST_URL",
    "MAX_DOWNLOAD",
    "OPENER",
    "TAIL_MAX",
    "TAIL_MIN",
    "TOTAL_SECONDS",
    "Entry",
    "FetchError",
    "http_get",
    "parse_listing",
    "tail_bytes",
]

_FILES = "https://data.gdeltproject.org/gdeltv2/"

LASTUPDATE_URL = {
    Stream.ENGLISH: _FILES + "lastupdate.txt",
    Stream.TRANSLATED: _FILES + "lastupdate-translation.txt",
}
MASTERLIST_URL = {
    Stream.ENGLISH: _FILES + "masterfilelist.txt",
    Stream.TRANSLATED: _FILES + "masterfilelist-translation.txt",
}

# A GKG zip is a few megabytes. Anything this large is not one, and is not read into memory.
MAX_DOWNLOAD = 256 * 1024 * 1024

# A download gets this long in all, and each read from the socket 60 seconds, so that it ends
# one way or the other inside the 5-minute lease. A step that outlasts its lease is repeated by
# another worker, which would then outlast its own.
TOTAL_SECONDS = 200.0
_CHUNK = 1024 * 1024

# One interval adds three lines of about 120 bytes to a master list. A tail read asks for a
# kibibyte per missing stamp, which is nearly three times that, and never fewer than TAIL_MIN.
# TAIL_MAX covers about four months of intervals by that arithmetic; stamps missed longer ago
# than one read reaches are enqueued with no listing.
TAIL_MIN = 64 * 1024
TAIL_MAX = 4 * 1024 * 1024
_TAIL_PER_STAMP = 1024

_LINE = re.compile(
    r"(\d{1,12}) ([0-9a-f]{32}) "
    r"https?://data\.gdeltproject\.org/gdeltv2/(\d{14})(\.translation)?\.gkg\.csv\.zip"
)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuses every redirect, so a 3xx answer is an error like any other status."""

    def redirect_request(self, *args: object, **kwargs: object) -> None:
        return None


OPENER = urllib.request.build_opener(_NoRedirect)


class FetchError(Exception):
    """A download that did not give the whole object: an HTTP status, a time-out, a dropped
    connection."""


@dataclass(frozen=True, slots=True)
class Entry:
    """What a listing says about one GKG file."""

    stamp: datetime
    size: int
    md5: str


def parse_listing(text: str, stream: Stream) -> dict[datetime, Entry]:
    """The GKG files of `stream` that `text` lists, by stamp.

    A line that is not a whole, well-formed GKG line of this stream is skipped: the other file
    types, the other stream, the bare directory lines the master lists contain, and the cut
    first line of a Range read. If a stamp is listed twice, its last line is kept.
    """
    entries: dict[datetime, Entry] = {}
    translated = stream is Stream.TRANSLATED
    for line in text.splitlines():
        match = _LINE.fullmatch(line)
        if match is None or (match.group(4) is not None) != translated:
            continue
        try:
            stamp = parse_stamp(match.group(3))
        except ValueError:
            continue
        entries[stamp] = Entry(stamp, int(match.group(1)), match.group(2))
    return entries


def tail_bytes(stamps: int) -> int:
    """How many bytes of a master list's end to read to cover the last `stamps` intervals."""
    return max(TAIL_MIN, min(TAIL_MAX, stamps * _TAIL_PER_STAMP + TAIL_MIN // 4))


def http_get(
    url: str, *, tail: int | None = None, timeout: float = 60.0, total: float = TOTAL_SECONDS
) -> bytes:
    """GET a file from GDELT, whole, or only its last `tail` bytes (a Range read).

    Raises FetchError when the object did not arrive whole within `total` seconds, and
    ValueError for a URL that is not in GDELT's HTTPS folder.
    """
    if not url.startswith(_FILES):
        raise ValueError(f"not a GDELT file: {url!r}")
    # A generic client name by default; GL_USER_AGENT sets the one production sends.
    agent = os.environ.get("GL_USER_AGENT", "gkg-poller/0.1")
    request = urllib.request.Request(url, headers={"User-Agent": agent})
    if tail is not None:
        request.add_header("Range", f"bytes=-{tail}")
    deadline = time.monotonic() + total
    chunks: list[bytes] = []
    size = 0
    try:
        with OPENER.open(request, timeout=timeout) as response:
            while True:
                chunk: bytes = response.read1(_CHUNK)
                if not chunk:
                    break
                chunks.append(chunk)
                size += len(chunk)
                if size > MAX_DOWNLOAD:
                    raise FetchError(f"more than {MAX_DOWNLOAD} bytes")
                if time.monotonic() > deadline:
                    raise FetchError(f"not finished after {total:.0f} seconds")
    except urllib.error.HTTPError as error:
        raise FetchError(f"HTTP {error.code}") from None
    except (OSError, http.client.HTTPException) as error:  # time-outs and resets are OSErrors
        raise FetchError(f"{type(error).__name__}: {error}") from None
    return b"".join(chunks)
