"""Reading GDELT's listing files: `lastupdate` and the tail of the master list.

The fixtures are synthetic: real file names, invented sizes and MD5s.
"""

import email.message
import io
import urllib.error
import urllib.request
from datetime import UTC, datetime

import pytest
from gdelt import Stream
from worker import feed

BASE = "http://data.gdeltproject.org/gdeltv2/"
MD5_A = "a" * 32
MD5_B = "b" * 32
MD5_C = "c" * 32

LASTUPDATE = (
    f"58168 {MD5_A} {BASE}20261120013000.export.CSV.zip\n"
    f"88685 {MD5_B} {BASE}20261120013000.mentions.CSV.zip\n"
    f"4473397 {MD5_C} {BASE}20261120013000.gkg.csv.zip\n"
)
LASTUPDATE_TRANSLATION = (
    f"40916 {MD5_A} {BASE}20261120011500.translation.export.CSV.zip\n"
    f"39329 {MD5_B} {BASE}20261120011500.translation.mentions.CSV.zip\n"
    f"5063415 {MD5_C} {BASE}20261120011500.translation.gkg.csv.zip\n"
)
# The tail of a master list as a Range read returns it: it starts in the middle of a line.
MASTER_TAIL = (
    ".mentions.CSV.zip\n"
    f"5367892 {MD5_A} {BASE}20261120003000.translation.gkg.csv.zip\n"
    f"56904 {MD5_B} {BASE}20261120004500.translation.export.CSV.zip\n"
    f"51680 {MD5_B} {BASE}20261120004500.translation.mentions.CSV.zip\n"
    f"5857490 {MD5_B} {BASE}20261120004500.translation.gkg.csv.zip\n"
    f"48134 {MD5_C} {BASE}20261120010000.translation.export.CSV.zip\n"
    f"43038 {MD5_C} {BASE}20261120010000.translation.mentions.CSV.zip\n"
    f"5990730 {MD5_C} {BASE}20261120010000.translation.gkg.csv.zip\n"
)


def at(hour: int, minute: int) -> datetime:
    return datetime(2026, 11, 20, hour, minute, tzinfo=UTC)


def test_lastupdate_gives_the_gkg_file_of_its_stream() -> None:
    assert feed.parse_listing(LASTUPDATE, Stream.ENGLISH) == {
        at(1, 30): feed.Entry(at(1, 30), 4473397, MD5_C)
    }
    assert feed.parse_listing(LASTUPDATE_TRANSLATION, Stream.TRANSLATED) == {
        at(1, 15): feed.Entry(at(1, 15), 5063415, MD5_C)
    }


def test_a_listing_of_the_other_stream_gives_nothing() -> None:
    assert feed.parse_listing(LASTUPDATE, Stream.TRANSLATED) == {}
    assert feed.parse_listing(LASTUPDATE_TRANSLATION, Stream.ENGLISH) == {}


def test_a_master_list_tail_gives_every_whole_gkg_line() -> None:
    assert feed.parse_listing(MASTER_TAIL, Stream.TRANSLATED) == {
        at(0, 30): feed.Entry(at(0, 30), 5367892, MD5_A),
        at(0, 45): feed.Entry(at(0, 45), 5857490, MD5_B),
        at(1, 0): feed.Entry(at(1, 0), 5990730, MD5_C),
    }


@pytest.mark.parametrize(
    "line",
    [
        "",
        "http://data.gdeltproject.org/gdeltv2/",  # the master lists hold bare directory lines
        f"4473397 {MD5_C}",
        f"{MD5_C} {BASE}20261120013000.gkg.csv.zip",
        f"x4473397 {MD5_C} {BASE}20261120013000.gkg.csv.zip",
        f"-1 {MD5_C} {BASE}20261120013000.gkg.csv.zip",
        f"4473397 {'g' * 32} {BASE}20261120013000.gkg.csv.zip",  # not hexadecimal
        f"4473397 {'A' * 32} {BASE}20261120013000.gkg.csv.zip",  # GDELT writes lower case
        f"4473397 {'a' * 31} {BASE}20261120013000.gkg.csv.zip",
        f"4473397 {MD5_C} {BASE}20261120013001.gkg.csv.zip",  # off the 15-minute grid
        f"4473397 {MD5_C} {BASE}20261320013000.gkg.csv.zip",  # month 13
        f"4473397 {MD5_C} {BASE}2026112001300.gkg.csv.zip",
        f"4473397 {MD5_C} {BASE}20261120013000.gkg.csv",
        f"4473397 {MD5_C} {BASE}20261120013000.gkg.csv.zip.part",
        f"4473397 {MD5_C} {BASE}sub/20261120013000.gkg.csv.zip",
        f"4473397 {MD5_C} http://example.org/gdeltv2/20261120013000.gkg.csv.zip",
        f"4473397 {MD5_C} ftp://data.gdeltproject.org/gdeltv2/20261120013000.gkg.csv.zip",
        f"4473397  {MD5_C} {BASE}20261120013000.gkg.csv.zip",  # two spaces
        f"4473397 {MD5_C} {BASE}20261120013000.gkg.csv.zip trailing",
    ],
)
def test_a_line_that_is_not_a_listing_is_skipped(line: str) -> None:
    assert feed.parse_listing(line + "\n", Stream.ENGLISH) == {}
    good = f"1 {MD5_A} {BASE}20261120011500.gkg.csv.zip\n"
    assert feed.parse_listing(line + "\n" + good, Stream.ENGLISH) == {
        at(1, 15): feed.Entry(at(1, 15), 1, MD5_A)
    }


def test_https_links_and_windows_line_ends_are_read_too() -> None:
    text = f"7 {MD5_A} https://data.gdeltproject.org/gdeltv2/20261120013000.gkg.csv.zip\r\n"
    assert feed.parse_listing(text, Stream.ENGLISH) == {at(1, 30): feed.Entry(at(1, 30), 7, MD5_A)}


def test_a_stamp_listed_twice_keeps_its_last_line() -> None:
    text = (
        f"7 {MD5_A} {BASE}20261120013000.gkg.csv.zip\n9 {MD5_B} {BASE}20261120013000.gkg.csv.zip\n"
    )
    assert feed.parse_listing(text, Stream.ENGLISH) == {at(1, 30): feed.Entry(at(1, 30), 9, MD5_B)}


def test_the_tail_read_grows_with_the_number_of_stamps_and_is_bounded() -> None:
    assert feed.tail_bytes(1) == feed.TAIL_MIN
    assert feed.tail_bytes(96) > feed.TAIL_MIN
    assert feed.tail_bytes(96) >= 96 * 3 * 130  # three lines an interval, about 120 bytes each
    sizes = [feed.tail_bytes(stamps) for stamps in range(1, 20_000, 97)]
    assert sizes == sorted(sizes)
    assert feed.tail_bytes(10_000_000) == feed.TAIL_MAX


def test_only_gdelts_own_https_files_are_fetched() -> None:
    for url in (
        "http://data.gdeltproject.org/gdeltv2/lastupdate.txt",
        "https://example.org/gdeltv2/lastupdate.txt",
        "https://data.gdeltproject.org.example.org/gdeltv2/lastupdate.txt",
        "file:///etc/hosts",
    ):
        with pytest.raises(ValueError):
            feed.http_get(url)


def test_the_listing_urls_are_gdelts() -> None:
    for urls in (feed.LASTUPDATE_URL, feed.MASTERLIST_URL):
        assert set(urls) == {Stream.ENGLISH, Stream.TRANSLATED}
        for url in urls.values():
            assert url.startswith("https://data.gdeltproject.org/gdeltv2/")
    assert "translation" in feed.LASTUPDATE_URL[Stream.TRANSLATED]
    assert "translation" not in feed.LASTUPDATE_URL[Stream.ENGLISH]
    assert "translation" in feed.MASTERLIST_URL[Stream.TRANSLATED]
    assert "translation" not in feed.MASTERLIST_URL[Stream.ENGLISH]


# --- http_get, with the opener replaced: no socket is opened ----------------------------------

URL = "https://data.gdeltproject.org/gdeltv2/lastupdate.txt"


class Response:
    """What an opener returns: a context manager that is read in pieces."""

    def __init__(self, pieces: list[bytes]) -> None:
        self.pieces = list(pieces)

    def __enter__(self) -> "Response":
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def read1(self, size: int) -> bytes:
        return self.pieces.pop(0) if self.pieces else b""


class Opener:
    def __init__(self, pieces: list[bytes] | None = None, error: Exception | None = None) -> None:
        self.pieces = pieces or []
        self.error = error
        self.requests: list[urllib.request.Request] = []

    def open(self, request: urllib.request.Request, timeout: float) -> Response:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return Response(self.pieces)


def test_a_download_is_its_pieces_joined(monkeypatch: pytest.MonkeyPatch) -> None:
    opener = Opener([b"ab", b"cd", b"e"])
    monkeypatch.setattr(feed, "OPENER", opener)
    monkeypatch.delenv("GL_USER_AGENT", raising=False)
    assert feed.http_get(URL) == b"abcde"
    (request,) = opener.requests
    assert request.full_url == URL
    assert request.get_header("User-agent") == "gkg-poller/0.1"
    assert request.get_header("Range") is None


def test_a_tail_read_asks_for_the_last_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    opener = Opener([b"tail"])
    monkeypatch.setattr(feed, "OPENER", opener)
    monkeypatch.setenv("GL_USER_AGENT", "a-client/1.0")
    assert feed.http_get(URL, tail=65536) == b"tail"
    (request,) = opener.requests
    assert request.get_header("Range") == "bytes=-65536"
    assert request.get_header("User-agent") == "a-client/1.0"


@pytest.mark.parametrize("status", [301, 302, 403, 404, 500, 503])
def test_any_status_but_success_is_a_fetch_error(
    monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    error = urllib.error.HTTPError(URL, status, "no", email.message.Message(), None)
    monkeypatch.setattr(feed, "OPENER", Opener(error=error))
    with pytest.raises(feed.FetchError, match=f"HTTP {status}"):
        feed.http_get(URL)


@pytest.mark.parametrize(
    "error",
    [TimeoutError("timed out"), ConnectionResetError("reset"), urllib.error.URLError("no route")],
)
def test_a_connection_that_fails_is_a_fetch_error(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    monkeypatch.setattr(feed, "OPENER", Opener(error=error))
    with pytest.raises(feed.FetchError):
        feed.http_get(URL)


def test_a_download_larger_than_the_limit_is_given_up(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(feed, "MAX_DOWNLOAD", 5)
    monkeypatch.setattr(feed, "OPENER", Opener([b"abc", b"de"]))
    assert feed.http_get(URL) == b"abcde"
    monkeypatch.setattr(feed, "OPENER", Opener([b"abc", b"def", b"never read"]))
    with pytest.raises(feed.FetchError, match="more than 5 bytes"):
        feed.http_get(URL)


def test_a_download_that_takes_too_long_is_given_up(monkeypatch: pytest.MonkeyPatch) -> None:
    # A time limit that has already passed: the first piece arrives too late.
    monkeypatch.setattr(feed, "OPENER", Opener([b"abc", b"def"]))
    with pytest.raises(feed.FetchError, match="not finished"):
        feed.http_get(URL, total=-1.0)
    # The limit leaves room inside a 5-minute lease for one last slow read.
    assert feed.TOTAL_SECONDS + 60 < 300


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_a_redirect_is_refused_not_followed(status: int) -> None:
    request = urllib.request.Request(URL)
    headers = email.message.Message()
    headers["Location"] = "https://example.org/elsewhere"
    with pytest.raises(urllib.error.HTTPError) as refused:
        feed.OPENER.error("http", request, io.BytesIO(b""), status, "Moved", headers)
    assert refused.value.code == status
