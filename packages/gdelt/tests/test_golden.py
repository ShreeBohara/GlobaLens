"""Golden GKG fixtures: shaped on real rows, carrying synthetic titles, URLs and outlet names.

Each `golden/NN_name.tsv` has a reviewed `golden/NN_name.json` holding what it must parse to.
The assertions written out below do not come from the parser: they state by hand what each
fixture is there to prove.
"""

import importlib.util
import json
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from gdelt import Issue, ParseResult, Reason, Stream, parse_gkg, result_to_json, title_hash

GOLDEN = Path(__file__).parent / "golden"
NAMES = sorted(path.stem for path in GOLDEN.glob("*.tsv"))

# Fixtures in which every line is a valid row: the contract must fail on none of them.
ALL_VALID = [
    "01_english_basic",
    "02_translated_entities",
    "06_bidi_zero_width",
    "07_locations_primary",
    "08_centroid_blocklist",
    "09_odd_fields",
    "10_urls",
    "11_languages",
    "12_long_title_and_whitespace",
]


def load(name: str) -> ParseResult:
    return parse_gkg((GOLDEN / f"{name}.tsv").read_bytes())


def test_there_are_at_least_ten_fixtures_each_with_its_expected_file() -> None:
    assert len(NAMES) >= 10
    for name in NAMES:
        assert (GOLDEN / f"{name}.json").is_file(), f"{name}.json is missing"
    assert set(ALL_VALID) <= set(NAMES)


@pytest.mark.parametrize("name", NAMES)
def test_fixture_parses_to_its_expected_file(name: str) -> None:
    expected = json.loads((GOLDEN / f"{name}.json").read_text(encoding="utf-8"))
    assert result_to_json(load(name)) == expected


@pytest.mark.parametrize("name", ALL_VALID)
def test_no_contract_failure_on_valid_rows(name: str) -> None:
    result = load(name)
    assert result.quarantined == []
    assert result.stats.quarantined == {}
    assert result.stats.rows == result.stats.lines > 0
    assert result.stats.malformed_share == 0.0


def test_the_committed_inputs_are_what_the_builder_writes() -> None:
    spec = importlib.util.spec_from_file_location("build_fixtures", GOLDEN / "build_fixtures.py")
    assert spec is not None and spec.loader is not None
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    assert sorted(builder.FIXTURES) == NAMES
    for name, build in builder.FIXTURES.items():
        assert (GOLDEN / f"{name}.tsv").read_bytes() == build(), f"{name}.tsv is stale"


def test_fixtures_name_no_real_outlet() -> None:
    """Titles, URLs and outlet names are synthetic (design note Q27): reserved domains only."""
    reserved = (".example", ".test")
    for name in NAMES:
        for raw in (GOLDEN / f"{name}.tsv").read_bytes().split(b"\n"):
            columns = raw.split(b"\t")
            if len(columns) != 27:
                continue
            outlet = columns[3].decode("utf-8", "replace")
            assert outlet.endswith(reserved), (name, outlet)
            url = columns[4].decode("utf-8", "replace")
            if url.lower().startswith(("http://", "https://")):
                host = (urlsplit(url).hostname or "").lower()
                assert host.endswith(reserved), (name, host)


def test_01_english_basic() -> None:
    first, second, third = load("01_english_basic").rows
    assert first.stream is Stream.ENGLISH and first.lang is not None and first.lang.tag == "en"
    assert first.record_id == "20260301120000-0" and first.seq == 0
    assert first.stamp == datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
    assert first.published_at == datetime(2026, 3, 1, 11, 30, tzinfo=UTC)
    assert first.outlet == "harbor-gazette.example"
    assert first.url == "https://www.harbor-gazette.example/world/2026/03/river-levels-rise"
    assert first.title == "River levels rise in the northern valley after a week of rain"
    assert first.title_hash == bytes.fromhex("a72c1b5983a5ff55")
    assert first.themes == ("NATURAL_DISASTER_FLOOD", "TAX_FNCACT_MAYOR", "WB_137_WATER")
    assert (
        first.tone is not None
        and first.tone.tone == -2.41545893719807
        and first.tone.word_count == 186
    )
    assert first.primary is not None and first.primary.is_point
    assert (first.primary.geo_type, first.primary.lat, first.primary.lon) == (4, 45.75, 4.85)
    # A bare ampersand is text; a US city (type 3) is a point; the US centroid is not chosen.
    assert second.title == "Harbor council approves R&D budget for tide gauges"
    assert second.primary is not None and (second.primary.geo_type, second.primary.adm1) == (
        3,
        "USTX",
    )
    assert second.published_at is None
    assert third.primary is None and third.locations == () and third.themes == ()
    assert third.url == "https://northern-courier.example/opinion/ferry-timetable/"


def test_02_translated_entities() -> None:
    result = load("02_translated_entities")
    zho, rus, ara, spa, jpn, deu = result.rows
    assert all(row.stream is Stream.TRANSLATED for row in result.rows)
    assert [row.seq for row in result.rows] == [3, 14, 205, 1206, 1207, 1208]
    assert zho.title == "测试标题:北方山谷河水上涨"  # the fullwidth colon is folded by NFKC
    assert zho.lang is not None and (zho.lang.tag, zho.srclc) == ("zh", "zho")
    assert rus.title == "Тестовый заголовок: уровень воды в реке растёт"
    assert (
        rus.translation_info == "srclc:rus;eng:Moses 2.1.1 / MosesCore Europarl ru-en / GT-RUS 1.0"
    )
    assert ara.title == "عنوان تجريبي: ارتفاع منسوب النهر في الوادي الشمالي"
    assert ara.lang is not None and ara.lang.direction == "rtl"
    assert spa.title == "Titular de prueba: «el río crece» – informe no 4"  # NFKC folds "º" to "o"
    assert jpn.title == "テスト見出し:2026年の川の水位(テスト)"
    assert deu.title == "Q&A: the mayor’s plan for R&D and &copy rules <draft>"
    assert result.stats.issues == {}


def test_03_malformed_column_counts() -> None:
    result = load("03_malformed_column_counts")
    assert [row.title for row in result.rows] == [
        "First synthetic headline",
        "Last synthetic headline",
    ]
    assert [(q.line_no, q.reason) for q in result.quarantined] == [
        (2, Reason.COLUMN_COUNT),  # 26 columns
        (3, Reason.COLUMN_COUNT),  # 28 columns
        (4, Reason.COLUMN_COUNT),  # one column of text
        (5, Reason.BAD_RECORD_ID),
        (6, Reason.BAD_DATE),  # too short
        (7, Reason.BAD_DATE),  # month 13
        (8, Reason.BAD_RECORD_ID),  # no record number
    ]
    assert result.stats.quarantined == {
        Reason.COLUMN_COUNT: 3,
        Reason.BAD_RECORD_ID: 2,
        Reason.BAD_DATE: 2,
    }
    assert (result.stats.lines, result.stats.rows) == (9, 2)
    assert result.stats.malformed_share == pytest.approx(7 / 9)
    raw_lines = (GOLDEN / "03_malformed_column_counts.tsv").read_bytes().split(b"\n")
    assert [q.raw for q in result.quarantined] == raw_lines[1:8], (
        "quarantine keeps the bytes as read"
    )


def test_04_broken_record_newlines() -> None:
    result = load("04_broken_record_newlines")
    before, head, after = result.rows
    assert (before.title, after.title) == ("Título de teste: antes", "Título de teste: depois")
    assert head.title is None and head.title_hash is None, "the lost title is not stitched back"
    assert head.url == "https://www.valley-dispatch.test/noticias/cortado"
    assert [(q.line_no, q.reason) for q in result.quarantined] == [
        (4, Reason.COLUMN_COUNT),
        (5, Reason.COLUMN_COUNT),
        (6, Reason.COLUMN_COUNT),
    ]
    assert result.stats.blank_lines == 1
    assert result.stats.issues == {Issue.TITLE_MISSING: 1}
    assert result.stats.malformed_share == pytest.approx(3 / 6)


def test_05_broken_utf8() -> None:
    result = load("05_broken_utf8")
    assert [row.seq for row in result.rows] == [0, 1, 2, 3, 7]
    assert result.rows[0].title == "Synthetic headline with a clean title"
    assert result.rows[1].title == "Caf\ufffd owners meet in the old town"
    assert result.rows[2].title == "Truncated headline \ufffd"
    assert result.rows[3].title == "Synthetic headline with a clean title"
    assert [(q.line_no, q.reason) for q in result.quarantined] == [
        (5, Reason.BAD_UTF8),  # the URL
        (6, Reason.BAD_UTF8),  # a location name
        (7, Reason.BAD_UTF8),  # the outlet
    ]
    assert result.stats.issues == {Issue.TITLE_BAD_UTF8: 2}


def test_06_bidi_zero_width() -> None:
    titles = [row.title for row in load("06_bidi_zero_width").rows]
    assert titles[0] == "Bank statement fdp.tnemetats"
    assert titles[1] == "عنوان تجريبي ثانٍ"
    assert titles[2] is not None and titles[2].count("\u200c") == 1, "ZWNJ is kept for Persian"
    assert titles[2] == unicodedata.normalize("NFKC", "عنوان آزمایشی: رودخانه بالا می\u200cآید")
    assert titles[3] is not None and titles[3].endswith("क्\u200dष"), "ZWJ is kept for Devanagari"
    assert titles[4] == "Weather update for the valley"
    assert titles[5] == "Rain – and more rain..."
    assert titles[6] == "Bell rings [31mred[0m in the square"
    assert titles[7] == "שלום עולם\u200f!"
    for title in titles:
        assert title is not None
        for ch in title:
            assert not 0x202A <= ord(ch) <= 0x202E and not 0x2066 <= ord(ch) <= 0x2069
            assert ch not in "\u200b\u2060\ufeff" and not 0xE0000 <= ord(ch) <= 0xE007F
            assert unicodedata.category(ch) != "Cc"


def test_07_locations_primary() -> None:
    rows = load("07_locations_primary").rows
    summary = [
        None
        if row.primary is None
        else (row.primary.geo_type, row.primary.name.split(",")[0], row.primary.lat)
        for row in rows
    ]
    assert summary == [
        (4, "Marseille", 43.3),
        (5, "Bayern", None),
        (2, "Ohio", None),
        (1, "Brazil", None),
        None,
        (3, "Austin", 30.2672),
        (5, "Ontario", None),
        (4, "Lyon", 45.75),
    ]
    assert [len(row.locations) for row in rows] == [3, 2, 2, 2, 0, 2, 2, 3]


def test_08_centroid_blocklist() -> None:
    result = load("08_centroid_blocklist")
    as_country, planted, with_city, with_state = (row.primary for row in result.rows)
    assert as_country is not None and planted is not None
    assert with_city is not None and with_state is not None
    assert (as_country.geo_type, as_country.country, as_country.lat, as_country.demoted) == (
        1,
        "US",
        None,
        False,
    )
    assert (planted.geo_type, planted.country, planted.adm1, planted.lat, planted.demoted) == (
        1,
        "US",
        "",
        None,
        True,
    )
    assert (with_city.geo_type, with_city.name.split(",")[0]) == (3, "Wichita")
    assert (with_state.geo_type, with_state.adm1) == (2, "USKS")
    for row in result.rows:
        assert row.primary is not None
        assert (row.primary.lat, row.primary.lon) != (39.828175, -98.5795), (
            "the centroid is never a point"
        )
    assert result.stats.issues == {Issue.CENTROID_DEMOTED: 1}


def test_09_odd_fields() -> None:
    result = load("09_odd_fields")
    rows = result.rows
    assert len(rows) == 13
    assert rows[0].primary is not None and rows[0].primary.name.startswith("Tbilisi")
    assert rows[1].primary is None and rows[1].locations == ()
    assert rows[2].primary is not None and (rows[2].primary.geo_type, rows[2].primary.country) == (
        1,
        "AA",
    )
    assert rows[3].tone is None and rows[4].tone is None
    assert rows[5].themes == ("TAX_FNCACT_MAYOR", "ENV_CLIMATECHANGE")
    assert rows[6].published_at is None and rows[7].published_at is None
    assert rows[6].title == "Synthetic headline with a dashed timestamp"
    assert [rows[i].title for i in (8, 9, 10, 12)] == [None, None, None, None]
    assert rows[11].primary is None and len(rows[11].locations) == 1
    assert result.stats.issues == {
        Issue.LOCATION_MALFORMED: 3,
        Issue.TONE_MALFORMED: 2,
        Issue.THEME_MALFORMED: 2,
        Issue.PUBLISHED_AT_INVALID: 2,
        Issue.TITLE_EMPTY: 2,
        Issue.TITLE_MISSING: 2,
    }


def test_10_urls() -> None:
    result = load("10_urls")
    site = "daily-lantern.example"
    assert [row.url for row in result.rows] == [
        f"https://www.{site}/story?id=71&page=2",
        f"http://{site}/a/",
        f"https://www.{site}/Path/Case?Q=1",
        f"https://{site}/a",
        None,  # ftp
        None,  # javascript:
        None,  # a citation, not a link
        f"https://{site}/",
        f"http://{site}:8080/a",
        f"https://{site}/a",
        f"https://{site}/caf%C3%A9/r%c3%ado?q=a%20b",
        None,  # a space inside the link
        f"https://{site}/río/测试",
    ]
    assert result.stats.issues == {Issue.URL_REJECTED: 4}


def test_11_languages() -> None:
    result = load("11_languages")
    tags = [None if row.lang is None else row.lang.tag for row in result.rows]
    assert tags == ["az", "fa", "he", "ur", "zh", None, None, "en", None, "sr"]
    assert [row.srclc for row in result.rows] == [
        "axe",
        "fas",
        "heb",
        "urd",
        "zho",
        "zzz",
        None,
        None,
        None,
        "srp",
    ]
    directions = [None if row.lang is None else row.lang.direction for row in result.rows]
    assert directions == ["ltr", "rtl", "rtl", "rtl", "ltr", None, None, "ltr", None, "ltr"]
    assert result.rows[7].stream is Stream.ENGLISH
    assert result.stats.unknown_srclc == {"zzz": 1}
    assert result.stats.issues == {
        Issue.SRCLC_UNKNOWN: 1,
        Issue.TRANSLATION_INFO_MISSING: 1,
        Issue.TRANSLATION_INFO_MALFORMED: 1,
    }


def test_12_long_title_and_whitespace() -> None:
    long_row, spaces, same_a, same_b, same_hidden, different = load(
        "12_long_title_and_whitespace"
    ).rows
    source = "Synthetic long headline " + "about the river and the valley " * 20
    assert long_row.title == source[:300].rstrip()
    assert long_row.title is not None and len(long_row.title) <= 300
    assert spaces.title == "Two spaces inside and around"
    assert (
        same_a.title
        == same_b.title
        == same_hidden.title
        == "Storm warning issued for the northern valley"
    )
    assert (
        same_a.title_hash
        == same_b.title_hash
        == same_hidden.title_hash
        == bytes.fromhex("b003c962cd5833d6")
    )
    assert different.title_hash != same_a.title_hash
    assert long_row.title_hash == title_hash(long_row.title)
