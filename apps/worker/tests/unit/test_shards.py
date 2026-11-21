"""The point shard and the title shards: each decodes back into exactly what went in, and the
same articles always give the same bytes.

Every title, URL and outlet name here is invented (`.example` domains).
"""

# h3 ships no type information, so its calls are unknown to pyright.
# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false

import hashlib
import logging
import math
import os
import random
import subprocess
import sys
from collections import Counter
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

import h3
import pytest
from gdelt import Stream, from_srclc, parse_gkg
from hypothesis import given
from hypothesis import strategies as st
from worker import lake, shards
from worker.cells import base_cell
from worker.shards import Article

STAMP = datetime(2026, 11, 20, 1, 30, tzinfo=UTC)
IV = shards.interval_index(STAMP)
KYIV = (50.45, 30.52)
LYON = (45.75, 4.85)
KANSAS = (39.828175, -98.5795)


def lang(code: str) -> int:
    found = from_srclc(code)
    assert found is not None
    return found.index


FRA, UKR, ENG = lang("fra"), lang("ukr"), lang("eng")


def article(record: int, **changes: Any) -> Article:
    """A city-level article in Lyon with a title, unless `changes` say otherwise."""
    base = Article(
        iv=IV,
        key=shards.make_key(Stream.TRANSLATED, record),
        lang=FRA,
        t=shards.minutes(STAMP) - record,
        outlet=f"outlet-{record % 4}.example",
        kind=4,
        code="",
        lat=LYON[0],
        lon=LYON[1],
        title=f"Synthetic headline {record}",
        url=f"https://outlet-{record % 4}.example/news/{record}",
        title_hash=hashlib.sha256(f"Synthetic headline {record}".encode()).digest()[:8],
    )
    return replace(base, **changes)


def area(record: int, kind: int, code: str, **changes: Any) -> Article:
    return article(record, kind=kind, code=code, lat=None, lon=None, **changes)


def mixed() -> list[Article]:
    """Points in two cells, country-level, US-state, ADM1 and unlocated articles, both streams,
    one untitled point and one article of an unknown language."""
    return [
        article(1),
        article(2, lat=KYIV[0], lon=KYIV[1], lang=UKR),
        article(3, key=shards.make_key(Stream.ENGLISH, 3), lang=ENG, kind=3),
        article(4, title=None, title_hash=None),
        article(5, url=None),
        area(6, 1, "UP"),
        area(7, 1, "UP"),
        area(8, 5, "UP12"),
        area(9, 2, "USTX", key=shards.make_key(Stream.ENGLISH, 9), lang=ENG),
        area(10, 0, ""),
        article(11, lang=shards.UNKNOWN_LANG),
        area(12, 1, "FR", lang=shards.UNKNOWN_LANG),
    ]


def expected_point(a: Article) -> shards.PointRow:
    assert a.lat is not None and a.lon is not None
    x, y, z = shards.quantize(a.lat, a.lon)
    return shards.PointRow(
        x=x,
        y=y,
        z=z,
        prec=a.kind,
        cell=base_cell(a.lat, a.lon),
        lang=a.lang,
        outlet=shards.outlet_hash(a.outlet),
        t=a.t,
        iv=a.iv,
        key=a.key,
    )


def by_identity(articles: list[Article]) -> list[Article]:
    return sorted(articles, key=lambda a: (a.iv, a.key))


# --- The point shard ---------------------------------------------------------------------


def test_a_point_shard_decodes_to_exactly_its_points_and_its_area_counts() -> None:
    articles = mixed()
    shard = shards.point_shard(articles)

    points = by_identity([a for a in articles if a.kind in (3, 4)])
    assert shards.read_points(shard.data, shard.points) == [expected_point(a) for a in points]
    assert shard.rows == len(points) == 6

    counts = Counter((a.kind, a.code, a.lang) for a in articles if a.kind not in (3, 4))
    expected = sorted(shards.AreaRow(k, c, lang, n) for (k, c, lang), n in counts.items())
    assert shards.read_areas(shard.data, shard.areas) == expected


def test_the_two_segments_are_two_whole_streams_back_to_back() -> None:
    shard = shards.point_shard(mixed())
    (p_start, p_length), (a_start, a_length) = shard.points, shard.areas
    assert p_start == 0
    assert a_start == p_length
    assert a_start + a_length == len(shard.data)
    assert p_length % 8 == 0 and a_length % 8 == 0
    # Each slice is readable on its own, the way the page reads it.
    assert len(shards.read_points(shard.data[:a_start], (0, p_length))) == 6
    assert len(shards.read_areas(shard.data[a_start:], (0, a_length))) > 0


def test_country_level_and_unlocated_articles_are_never_points() -> None:
    articles = [
        area(n, kind, code)
        for n, (kind, code) in enumerate([(1, "UP"), (2, "USTX"), (5, "UP12"), (0, "")])
    ]
    shard = shards.point_shard(articles)
    assert shards.read_points(shard.data, shard.points) == []
    assert shard.rows == 0
    assert sum(row.n for row in shards.read_areas(shard.data, shard.areas)) == 4


def test_a_point_on_a_blocklisted_centroid_is_refused() -> None:
    with pytest.raises(ValueError, match="blocklisted"):
        shards.point_shard([article(1, lat=KANSAS[0], lon=KANSAS[1])])


def test_a_point_without_coordinates_is_refused() -> None:
    with pytest.raises(ValueError, match="coordinates"):
        shards.point_shard([article(1, lat=None, lon=None)])


@given(
    st.floats(min_value=-90, max_value=90, allow_nan=False),
    st.floats(min_value=-180, max_value=180, allow_nan=False),
)
def test_a_vector_normalized_at_decode_is_within_one_quantization_step(
    lat: float, lon: float
) -> None:
    x, y, z = shards.quantize(lat, lon)
    assert all(-32767 <= v <= 32767 for v in (x, y, z))
    # What the page does (docs/design/p1.md §6.3.1): divide by 32767, then by the length.
    length = math.sqrt(x * x + y * y + z * z)
    decoded = (x / length, y / length, z / length)
    phi, lam = math.radians(lat), math.radians(lon)
    true = (math.cos(phi) * math.cos(lam), math.cos(phi) * math.sin(lam), math.sin(phi))
    chord = math.dist(decoded, true)
    assert chord <= 1 / 32767


def test_the_schemas_name_themselves_and_the_language_table() -> None:
    shard = shards.point_shard(mixed())
    cells, country = shards.title_shards(mixed())
    assert country is not None
    for data, segment, name in [
        (shard.data, shard.points, "points/1"),
        (shard.data, shard.areas, "areas/1"),
        (cells[0].data, (0, len(cells[0].data)), "titles/1"),
        (country.data, (0, len(country.data)), "country-titles/1"),
    ]:
        metadata = shards.schema_metadata(data, segment)
        assert metadata["gl.schema"] == name
        assert metadata["gl.langs"] == str(shards.LANG_TABLE_VERSION)


# --- The title shards --------------------------------------------------------------------


def expected_title(a: Article, *, country: bool) -> shards.TitleRow:
    assert a.title is not None and a.title_hash is not None
    return shards.TitleRow(
        iv=a.iv,
        key=a.key,
        lang=a.lang,
        t=a.t,
        title=a.title,
        url=a.url,
        outlet=a.outlet,
        title_hash=a.title_hash,
        kind=a.kind if country else None,
        code=a.code if country else None,
    )


def test_title_shards_decode_to_exactly_their_titles() -> None:
    articles = mixed()
    cells, country = shards.title_shards(articles)

    titled_points = by_identity([a for a in articles if a.kind in (3, 4) and a.title])
    by_cell: dict[int, list[Article]] = {}
    for a in titled_points:
        assert a.lat is not None and a.lon is not None
        by_cell.setdefault(base_cell(a.lat, a.lon), []).append(a)
    assert sorted(cell for shard in cells for cell in shard.cells) == sorted(by_cell)
    for shard in cells:
        (cell,) = shard.cells
        rows = shards.read_titles(shard.data)
        assert rows == [expected_title(a, country=False) for a in by_cell[cell]]
        assert shard.rows == len(rows)

    assert country is not None
    titled_areas = by_identity([a for a in articles if a.kind in (1, 2, 5) and a.title])
    assert shards.read_titles(country.data) == [
        expected_title(a, country=True) for a in titled_areas
    ]
    assert country.cells == ()


def test_an_untitled_article_is_a_point_with_no_title_row() -> None:
    articles = [article(1), article(2, title=None, title_hash=None)]
    shard = shards.point_shard(articles)
    assert len(shards.read_points(shard.data, shard.points)) == 2
    cells, country = shards.title_shards(articles)
    assert [row.key for shard_ in cells for row in shards.read_titles(shard_.data)] == [
        articles[0].key
    ]
    assert country is None


def test_unlocated_articles_have_no_title_row() -> None:
    cells, country = shards.title_shards([area(1, 0, "")])
    assert cells == [] and country is None


def spread(cell_count: int) -> list[Article]:
    """Titled points in `cell_count` different base cells, cell i holding i + 1 articles."""
    centres = [h3.cell_to_latlng(c) for c in sorted(h3.get_res0_cells())]
    articles: list[Article] = []
    record = 1000  # clear of the record numbers of mixed()
    for i in range(cell_count):
        lat, lon = centres[i]
        for _ in range(i + 1):
            record += 1
            articles.append(article(record, lat=lat, lon=lon))
    return articles


def test_at_most_60_title_objects_the_quietest_cells_sharing_one() -> None:
    articles = spread(70)
    cells, _ = shards.title_shards(articles)
    assert len(cells) == shards.MAX_TITLE_SHARDS == 60
    covered = [cell for shard in cells for cell in shard.cells]
    places = {(a.lat, a.lon) for a in articles if a.lat is not None and a.lon is not None}
    assert sorted(covered) == sorted({base_cell(lat, lon) for lat, lon in places})
    assert len(covered) == len(set(covered)) == 70
    shared = [shard for shard in cells if len(shard.cells) > 1]
    assert len(shared) == 1
    # The 11 quietest cells (1 to 11 articles each) share the last object.
    assert shared[0].rows == sum(range(1, 12))
    every_row = sorted(row.key for shard in cells for row in shards.read_titles(shard.data))
    assert every_row == sorted(a.key for a in articles)


def test_a_lower_limit_merges_more_cells() -> None:
    cells, _ = shards.title_shards(spread(70), limit=59)
    assert len(cells) == 59
    assert sum(len(shard.cells) for shard in cells) == 70
    assert [len(shard.cells) for shard in cells].count(12) == 1  # the 12 quietest share one


def test_the_limit_is_at_least_one() -> None:
    with pytest.raises(ValueError):
        shards.title_shards(spread(3), limit=0)


def test_60_cells_or_fewer_get_one_object_each() -> None:
    cells, _ = shards.title_shards(spread(60))
    assert len(cells) == 60
    assert all(len(shard.cells) == 1 for shard in cells)


# --- Bytes -------------------------------------------------------------------------------


def all_bytes(articles: list[Article]) -> list[bytes]:
    shard = shards.point_shard(articles)
    cells, country = shards.title_shards(articles)
    return [shard.data, *(c.data for c in cells), *([country.data] if country else [])]


def test_the_same_articles_give_the_same_bytes_in_any_order() -> None:
    articles = mixed() + spread(5)
    first = all_bytes(articles)
    shuffled = list(articles)
    random.Random(7).shuffle(shuffled)
    assert all_bytes(shuffled) == first


def test_different_articles_give_different_bytes() -> None:
    one = all_bytes(mixed())
    two = all_bytes([*mixed()[:-1], area(12, 1, "FR", lang=ENG)])
    assert one[0] != two[0]


DIGESTS = """
import hashlib, sys
sys.path.insert(0, sys.argv[1])
from test_shards import all_bytes, mixed, spread
print(" ".join(hashlib.sha256(b).hexdigest() for b in all_bytes(mixed() + spread(5))))
"""


def test_another_process_with_another_hash_seed_gives_the_same_bytes() -> None:
    here = " ".join(hashlib.sha256(b).hexdigest() for b in all_bytes(mixed() + spread(5)))
    for seed in ("1", "2"):
        other = subprocess.run(
            [sys.executable, "-c", DIGESTS, os.path.dirname(__file__)],
            capture_output=True,
            env={**os.environ, "PYTHONHASHSEED": seed},
            timeout=120,
            check=False,
        )
        assert other.returncode == 0, other.stderr.decode()
        assert other.stdout.decode().strip() == here


# --- Identity and the lake ---------------------------------------------------------------


def gkg_line(stream: Stream, stamp: datetime, number: int, location: str, extras: str) -> bytes:
    text = stamp.strftime("%Y%m%d%H%M%S")
    translated = stream is Stream.TRANSLATED
    columns = [""] * 27
    columns[0] = f"{text}-{'T' if translated else ''}{number}"
    columns[1] = text
    columns[2] = "1"
    columns[3] = f"outlet-{number % 3}.example"
    columns[4] = f"https://outlet-{number % 3}.example/{stream.value}/{number}"
    columns[10] = location
    columns[15] = "-2.5,1.5,4,5.5,20,0.5,310"
    columns[25] = "srclc:ukr;eng:GT-UKR 1.0" if translated else ""
    columns[26] = extras
    return "\t".join(columns).encode()


LOCATIONS = [
    "4#Kyiv, Kyiv, Ukraine#UP#UP12#80247#50.4333#30.5167#-1044367#40",
    "1#Ukraine#UP#UP##49#32#UP#10",
    "5#Kyiv, Ukraine#UP#UP12##50.4333#30.5167#-1044367#40",
    "2#Texas, United States#US#USTX##31.106#-97.6475#TX#1120",
    "",
    "4#Kansas#US#USKS#KS#39.828175#-98.5795#KS#12",  # the blocklisted centroid: country-level
    "3#Austin, Texas, United States#US#USTX#TX453#30.2672#-97.7431#1384879#977",
]


PUBLISHED = "<PAGE_PRECISEPUBTIMESTAMP>20261120011200</PAGE_PRECISEPUBTIMESTAMP>"


def lake_file(stream: Stream, stamp: datetime) -> tuple[bytes, bytes, list[str]]:
    lines = []
    for number, location in enumerate(LOCATIONS * 2, start=1):
        published = "" if number % 2 else PUBLISHED
        title = "" if number == 3 else f"<PAGE_TITLE>Synthetic headline {number}</PAGE_TITLE>"
        lines.append(gkg_line(stream, stamp, number, location, title + published))
    parsed = parse_gkg(b"\n".join(lines) + b"\n")
    assert parsed.stats.rows == len(lines)
    facts, display = lake.build(parsed.rows, parsed.stats)
    return facts, display, [row.record_id for row in parsed.rows]


@pytest.mark.parametrize("stream", list(Stream))
def test_articles_read_from_the_lake_carry_the_rows_identity_and_place(stream: Stream) -> None:
    facts, display, record_ids = lake_file(stream, STAMP)
    articles = shards.read_articles(stream, STAMP, facts, display)

    assert [shards.record_id(a.iv, a.key) for a in articles] == record_ids
    assert {a.iv for a in articles} == {IV}
    assert {a.lang for a in articles} == {UKR if stream is Stream.TRANSLATED else ENG}

    places = [(a.kind, a.code, a.lat is not None) for a in articles[: len(LOCATIONS)]]
    assert places == [
        (4, "", True),
        (1, "UP", False),
        (5, "UP12", False),
        (2, "USTX", False),
        (0, "", False),
        (1, "US", False),  # demoted by the parser: a centroid is never a point
        (3, "", True),
    ]
    published = shards.minutes(datetime(2026, 11, 20, 1, 12, tzinfo=UTC))
    assert [a.t for a in articles[:2]] == [shards.minutes(STAMP), published]
    assert articles[2].title is None and articles[2].title_hash is None
    assert articles[0].title == "Synthetic headline 1"
    assert articles[0].url == "https://outlet-1.example/" + stream.value + "/1"
    assert articles[0].outlet == "outlet-1.example"


def test_both_streams_share_one_shard_without_a_collision() -> None:
    english = shards.read_articles(Stream.ENGLISH, STAMP, *lake_file(Stream.ENGLISH, STAMP)[:2])
    translated = shards.read_articles(
        Stream.TRANSLATED, STAMP, *lake_file(Stream.TRANSLATED, STAMP)[:2]
    )
    shard = shards.point_shard(english + translated)
    rows = shards.read_points(shard.data, shard.points)
    ids = [shards.record_id(row.iv, row.key) for row in rows]
    assert len(ids) == len(set(ids)) == 8  # Kyiv and Austin, twice, in each stream
    assert sum("-T" in i for i in ids) == 4


def repeated_lake_file(stream: Stream, stamp: datetime, batches: list[int]) -> tuple[bytes, bytes]:
    """A lake file as GDELT sometimes writes one: several batches in one file, each numbering
    its records from 0 again."""
    lines = []
    serial = 0
    for size in batches:
        for number in range(size):
            serial += 1
            title = f"<PAGE_TITLE>Synthetic headline {serial}</PAGE_TITLE>"
            lines.append(gkg_line(stream, stamp, number, LOCATIONS[serial % 3], title))
    parsed = parse_gkg(b"\n".join(lines) + b"\n")
    return lake.build(parsed.rows, parsed.stats)


def test_a_record_number_that_comes_back_in_its_file_gets_the_repeat_bit() -> None:
    facts, display = repeated_lake_file(Stream.TRANSLATED, STAMP, [5, 3])
    articles = shards.read_articles(Stream.TRANSLATED, STAMP, facts, display)
    assert len(articles) == 8
    keys = [(a.iv, a.key) for a in articles]
    assert len(set(keys)) == 8  # one identity per row
    assert [shards.is_repeat(a.key) for a in articles] == [False] * 5 + [True] * 3
    # Both rows keep the record ID GDELT gave them.
    ids = [shards.record_id(a.iv, a.key) for a in articles]
    assert ids == [f"20261120013000-T{n}" for n in [0, 1, 2, 3, 4, 0, 1, 2]]
    assert articles[0].title != articles[5].title
    shard = shards.point_shard(articles)  # no longer two rows with one identity
    cells, country = shards.title_shards(articles)
    titled = [row for c in cells for row in shards.read_titles(c.data)]
    titled += shards.read_titles(country.data) if country else []
    assert sorted((r.iv, r.key) for r in titled) == sorted(keys)  # every row titled, once
    assert shard.rows == sum(1 for a in articles if a.kind in (3, 4))


def test_a_third_appearance_is_left_out_with_a_warning(caplog: pytest.LogCaptureFixture) -> None:
    facts, display = repeated_lake_file(Stream.TRANSLATED, STAMP, [2, 2, 2])
    with caplog.at_level(logging.WARNING, logger="worker.shards"):
        articles = shards.read_articles(Stream.TRANSLATED, STAMP, facts, display)
    assert len(articles) == 4
    assert "appears 3 times" in caplog.text
    assert "Synthetic" not in caplog.text  # never a title in a log


def odd_lake_file(
    stream: Stream, ids: list[str], extras: list[str] | None = None
) -> tuple[bytes, bytes]:
    """A lake file whose rows carry these record IDs as written, each with a title."""
    lines = []
    for n, identity in enumerate(ids):
        line = gkg_line(
            stream, STAMP, n, LOCATIONS[0], f"<PAGE_TITLE>Synthetic headline {n}</PAGE_TITLE>"
        )
        columns = line.split(b"\t")
        columns[0] = identity.encode()
        if extras is not None:
            columns[26] += extras[n].encode()
        lines.append(b"\t".join(columns))
    parsed = parse_gkg(b"\n".join(lines) + b"\n")
    assert parsed.stats.rows == len(ids), parsed.stats.quarantined
    return lake.build(parsed.rows, parsed.stats)


@pytest.mark.parametrize(
    "ids",
    [
        ["20261120013000-5", "20261120013000-05"],  # a leading zero: the same record number
        ["20261120013000-5", "20261120013000-T5"],  # a T in the English stream
    ],
)
def test_two_rows_that_would_share_a_key_both_become_articles(ids: list[str]) -> None:
    articles = shards.read_articles(Stream.ENGLISH, STAMP, *odd_lake_file(Stream.ENGLISH, ids))
    assert len({(a.iv, a.key) for a in articles}) == 2
    assert [shards.is_repeat(a.key) for a in articles] == [False, True]
    shards.point_shard(articles)  # and the shard is written
    shards.title_shards(articles)


def test_a_record_id_that_names_another_time_stays_in_its_interval() -> None:
    ids = ["20261120013100-1", "20261120020000-2"]  # off the grid; another interval
    articles = shards.read_articles(Stream.ENGLISH, STAMP, *odd_lake_file(Stream.ENGLISH, ids))
    assert {a.iv for a in articles} == {IV}
    shards.point_shard(articles)


def test_a_publication_time_the_column_cannot_hold_falls_back_to_the_stamp() -> None:
    far = "<PAGE_PRECISEPUBTIMESTAMP>99991231235959</PAGE_PRECISEPUBTIMESTAMP>"
    near = "<PAGE_PRECISEPUBTIMESTAMP>20261120011200</PAGE_PRECISEPUBTIMESTAMP>"
    ids = ["20261120013000-1", "20261120013000-2"]
    facts, display = odd_lake_file(Stream.ENGLISH, ids, [far, near])
    articles = shards.read_articles(Stream.ENGLISH, STAMP, facts, display)
    assert [a.t for a in articles] == [
        shards.minutes(STAMP),
        shards.minutes(datetime(2026, 11, 20, 1, 12, tzinfo=UTC)),
    ]
    shards.point_shard(articles)


def test_interval_numbers_and_keys() -> None:
    assert shards.interval_index(datetime(1970, 1, 1, tzinfo=UTC)) == 0
    assert shards.interval_index(datetime(1970, 1, 1, 0, 15, tzinfo=UTC)) == 1
    assert shards.stamp_of(IV) == STAMP
    assert shards.stamp_of(IV + 1) == STAMP + timedelta(minutes=15)
    assert shards.make_key(Stream.ENGLISH, 7) == 7
    assert shards.make_key(Stream.TRANSLATED, 7) == 2**31 + 7
    assert shards.record_id(IV, shards.make_key(Stream.TRANSLATED, 42)) == "20261120013000-T42"
    assert shards.record_id(IV, shards.make_key(Stream.ENGLISH, 42)) == "20261120013000-42"
    assert shards.make_key(Stream.TRANSLATED, 7, repeat=True) == 2**31 + 2**30 + 7
    assert shards.record_id(IV, shards.make_key(Stream.ENGLISH, 42, repeat=True)) == (
        "20261120013000-42"
    )
    assert shards.make_key(Stream.ENGLISH, 999_999_999) == 999_999_999  # the contract's largest
    with pytest.raises(ValueError):
        shards.make_key(Stream.ENGLISH, 2**30)
    with pytest.raises(ValueError):
        shards.interval_index(datetime(2026, 11, 20, 1, 31, tzinfo=UTC))


def test_the_outlet_hash_is_the_first_four_bytes_of_sha256() -> None:
    digest = hashlib.sha256(b"outlet-1.example").digest()
    assert shards.outlet_hash("outlet-1.example") == int.from_bytes(digest[:4], "big")
