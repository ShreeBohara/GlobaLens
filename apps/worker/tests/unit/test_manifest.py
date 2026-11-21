"""The data plane's JSON files read back into exactly what was written, as the same bytes for
the same content."""

import json
from datetime import UTC, datetime, timedelta

import pytest
from gdelt import Stream
from worker import manifest
from worker.manifest import (
    Hour,
    HourManifest,
    Now,
    PassManifest,
    Points,
    Ref,
    StreamClock,
    TitleIndex,
    Unit,
)

STAMP = datetime(2026, 11, 14, 14, 0, tzinfo=UTC)
KEY = "live/dt=2026-11-14/shards/" + "a" * 32 + ".arrow"


def points() -> Points:
    return Points(ref=Ref(KEY, 42104, 1893), points=(0, 39820), areas=(39820, 2284))


def titles() -> TitleIndex:
    shared = Ref("live/dt=2026-11-14/titles/" + "c" * 32 + ".arrow", 900, 4)
    return TitleIndex(
        cells={
            12: Ref("live/dt=2026-11-14/titles/" + "b" * 32 + ".arrow", 18230, 96),
            100: shared,
            101: shared,
        },
        country=Ref("live/dt=2026-11-14/titles/" + "d" * 32 + ".arrow", 40112, 511),
    )


def test_now_json_reads_back() -> None:
    now = Now(
        seq=4812,
        written_at=STAMP + timedelta(minutes=11, seconds=7),
        manifest="live/dt=2026-11-14/manifest/" + "9" * 32 + ".json",
        streams={
            Stream.ENGLISH: StreamClock(STAMP, STAMP - timedelta(minutes=8, seconds=50)),
            Stream.TRANSLATED: None,
        },
    )
    data = now.bytes()
    assert manifest.read_now(data) == now
    assert json.loads(data) == {
        "v": 1,
        "seq": 4812,
        "written_at": "2026-11-14T14:11:07Z",
        "manifest": now.manifest,
        "streams": {
            "english": {"stamp": "2026-11-14T14:00:00Z", "listed_at": "2026-11-14T13:51:10Z"},
            "translated": None,
        },
    }


def test_a_pass_manifest_reads_back() -> None:
    units = (
        Unit(STAMP, (Stream.ENGLISH, Stream.TRANSLATED), points(), titles()),
        Unit(STAMP, (Stream.TRANSLATED,), points(), TitleIndex(cells={}, country=None)),
    )
    written = PassManifest(seq=7, written_at=STAMP, hour="live/x/manifest/h.json", open=units)
    read = manifest.read_pass_manifest(written.bytes())
    assert read.seq == 7 and read.written_at == STAMP and read.hour == "live/x/manifest/h.json"
    assert tuple(read.open) == units
    assert json.loads(written.bytes())["open"][0]["points"]["segments"] == {
        "points": [0, 39820],
        "areas": [39820, 2284],
    }


def test_an_hourly_manifest_reads_back() -> None:
    hour = Hour(
        hour=STAMP,
        stamps={
            Stream.ENGLISH: (STAMP, STAMP + timedelta(minutes=15)),
            Stream.TRANSLATED: (),
        },
        points=points(),
        titles=Ref("live/dt=2026-11-14/hour/" + "e" * 32 + ".json", 3000, 0),
    )
    written = HourManifest(cut=STAMP + timedelta(hours=1, minutes=15), hours=(hour,))
    read = manifest.read_hour_manifest(written.bytes())
    assert read.cut == written.cut
    assert tuple(read.hours) == (hour,)


def test_a_title_index_reads_back() -> None:
    data = manifest.title_index_bytes(STAMP, titles())
    assert manifest.read_title_index(data) == (STAMP, titles())


def test_the_same_content_gives_the_same_bytes() -> None:
    one = PassManifest(
        seq=1,
        written_at=STAMP,
        hour=None,
        open=(Unit(STAMP, (Stream.ENGLISH,), points(), titles()),),
    )
    two = PassManifest(
        seq=1,
        written_at=STAMP,
        hour=None,
        open=(Unit(STAMP, (Stream.ENGLISH,), points(), titles()),),
    )
    assert one.bytes() == two.bytes()
    assert b" " not in one.bytes()


def test_a_file_of_another_version_is_refused() -> None:
    with pytest.raises(ValueError, match="version"):
        manifest.read_now(b'{"v": 2}')
    with pytest.raises(ValueError, match="version"):
        manifest.read_pass_manifest(b"[]")


def test_times_are_utc_with_a_z() -> None:
    assert manifest.time_text(datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)) == "2026-01-02T03:04:05Z"
    with pytest.raises(ValueError):
        manifest.time_text(datetime(2026, 1, 2))
