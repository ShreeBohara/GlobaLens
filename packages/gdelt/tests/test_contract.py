"""The row contract: exactly 27 tab-separated columns, a usable record ID and date, valid UTF-8
in the columns that are kept. A row that fails is counted and quarantined, never guessed at."""

from collections import Counter
from datetime import UTC, datetime

import pytest
from gdelt import (
    COLUMN_COUNT,
    ENGLISH,
    Issue,
    LeanRow,
    Reason,
    RowRejected,
    Stream,
    Tone,
    parse_gkg,
    parse_line,
)

TONE = "-2.5,1.5,4,5.5,21.25,0.5,186"
LYON = "4#Lyon, Rhone-Alpes, France#FR#FRB9#69#45.75#4.85#-1445171#58"
CENTROID_AS_CITY = "3#Somewhere, Kansas, United States#US#USKS#KS000#39.828175#-98.5795#999999#10"
BAD_RECORD_IDS = [
    "",
    "not-a-record-id",
    "20260301120000",
    "20260301120000-",
    "20260301120000-T",
    "2026030112000-1",
    "20260301120000-X1",
    "20260301120000-1 ",
    "20260301120000-t1",
    "20260301120000--1",
    "20261301120000-1",
]
EXTRAS = (
    "<PAGE_LINKS>https://harbor-gazette.example/a</PAGE_LINKS>"
    "<PAGE_PRECISEPUBTIMESTAMP>20260301113000</PAGE_PRECISEPUBTIMESTAMP>"
    "<PAGE_TITLE>River levels rise in the northern valley</PAGE_TITLE>"
)


def make_row(**overrides: str | bytes) -> bytes:
    columns: dict[int, str | bytes] = dict.fromkeys(range(COLUMN_COUNT), "dropped column")
    columns.update(
        {
            0: "20260301120000-42",
            1: "20260301120000",
            2: "1",
            3: "harbor-gazette.example",
            4: "https://www.harbor-gazette.example/world/river?utm_source=feed",
            8: "NATURAL_DISASTER_FLOOD,45;TAX_FNCACT_MAYOR,210;NATURAL_DISASTER_FLOOD,388;",
            10: f"{LYON};1#France#FR#FR##46#2#FR#301",
            15: TONE,
            25: "",
            26: EXTRAS,
        }
    )
    names = {
        "record_id": 0,
        "date": 1,
        "outlet": 3,
        "url": 4,
        "themes": 8,
        "locations": 10,
        "tone": 15,
        "translation_info": 25,
        "extras": 26,
        "gcam": 17,
    }
    for name, value in overrides.items():
        columns[names[name]] = value
    return b"\t".join(v if isinstance(v, bytes) else v.encode() for v in columns.values())


def test_the_contract_is_27_columns() -> None:
    assert COLUMN_COUNT == 27
    assert make_row().count(b"\t") == 26


def test_a_valid_row_gives_the_lean_projection() -> None:
    row = parse_line(make_row())
    assert isinstance(row, LeanRow)
    assert row.record_id == "20260301120000-42"
    assert row.stream is Stream.ENGLISH and row.seq == 42
    assert row.stamp == datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
    assert row.outlet == "harbor-gazette.example"
    assert row.url == "https://www.harbor-gazette.example/world/river"
    assert row.title == "River levels rise in the northern valley"
    assert row.title_hash is not None and len(row.title_hash) == 8
    assert row.published_at == datetime(2026, 3, 1, 11, 30, tzinfo=UTC)
    assert row.lang is ENGLISH and row.srclc is None and row.translation_info == ""
    assert row.tone == Tone(-2.5, 1.5, 4.0, 5.5, 21.25, 0.5, 186.0)
    assert row.themes == ("NATURAL_DISASTER_FLOOD", "TAX_FNCACT_MAYOR")
    assert len(row.locations) == 2
    assert row.primary is not None and row.primary.name.startswith("Lyon")


def test_a_translated_row() -> None:
    row = parse_line(
        make_row(
            record_id="20260301120000-T7",
            translation_info="srclc:fra;eng:Moses 2.1.1 / MosesCore Europarl fr-en / GT-FRA 1.0",
            extras="<PAGE_TITLE>Titre d&#x27;essai : la rivi&#xE8;re monte</PAGE_TITLE>",
        )
    )
    assert row.stream is Stream.TRANSLATED and row.seq == 7
    assert row.srclc == "fra" and row.lang is not None and row.lang.tag == "fr"
    assert row.translation_info.startswith("srclc:fra;eng:Moses")
    assert row.title == "Titre d'essai : la rivière monte"
    assert row.published_at is None


@pytest.mark.parametrize("count", [0, 1, 2, 26, 28, 30, 61])
def test_any_other_column_count_is_rejected(count: int) -> None:
    line = b"\t".join([b"x"] * count)
    with pytest.raises(RowRejected) as caught:
        parse_line(line)
    assert caught.value.reason is Reason.COLUMN_COUNT


@pytest.mark.parametrize("record_id", BAD_RECORD_IDS)
def test_an_unusable_record_id_is_rejected(record_id: str) -> None:
    with pytest.raises(RowRejected) as caught:
        parse_line(make_row(record_id=record_id))
    assert caught.value.reason is Reason.BAD_RECORD_ID


@pytest.mark.parametrize(
    "date",
    [
        "",
        "2026030112",
        "20261301120000",
        "20260230120000",
        "20260301250000",
        "2026-03-01 12:00",
        "20260301120000 ",
    ],
)
def test_an_unusable_date_is_rejected(date: str) -> None:
    with pytest.raises(RowRejected) as caught:
        parse_line(make_row(date=date))
    assert caught.value.reason is Reason.BAD_DATE


@pytest.mark.parametrize(
    "column", ["outlet", "url", "themes", "locations", "tone", "translation_info"]
)
def test_broken_utf8_in_a_kept_column_is_rejected(column: str) -> None:
    with pytest.raises(RowRejected) as caught:
        parse_line(make_row(**{column: b"caf\xe9"}))
    assert caught.value.reason is Reason.BAD_UTF8


def test_dropped_columns_are_never_read() -> None:
    row = parse_line(make_row(gcam=b"wc:10,\xff\xfe\x00 anything at all"))
    assert row.title == "River levels rise in the northern valley"


def test_broken_utf8_in_the_title_is_marked_not_guessed() -> None:
    issues: Counter[str] = Counter()
    row = parse_line(make_row(extras=b"<PAGE_TITLE>Caf\xe9 owners meet</PAGE_TITLE>"), issues)
    assert row.title == "Caf\ufffd owners meet"
    assert issues == {Issue.TITLE_BAD_UTF8: 1}


def test_broken_utf8_elsewhere_in_the_extras_does_not_matter() -> None:
    issues: Counter[str] = Counter()
    extras = (
        b"<PAGE_ALTURL_AMP>https://x.example/caf\xe9</PAGE_ALTURL_AMP>"
        b"<PAGE_TITLE>Clean title</PAGE_TITLE>"
    )
    assert parse_line(make_row(extras=extras), issues).title == "Clean title"
    assert not issues


@pytest.mark.parametrize(
    ("extras", "issue"),
    [
        ("", Issue.TITLE_MISSING),
        ("<PAGE_AUTHORS>Jane Example</PAGE_AUTHORS>", Issue.TITLE_MISSING),
        ("<PAGE_TITLE>never closed", Issue.TITLE_MISSING),
        ("<PAGE_TITLE></PAGE_TITLE>", Issue.TITLE_EMPTY),
        ("<PAGE_TITLE> &#x200B; </PAGE_TITLE>", Issue.TITLE_EMPTY),
    ],
)
def test_a_row_without_a_title_is_still_a_row(extras: str, issue: Issue) -> None:
    issues: Counter[str] = Counter()
    row = parse_line(make_row(extras=extras), issues)
    assert row.title is None and row.title_hash is None
    assert issues == {issue: 1}


@pytest.mark.parametrize(
    "stamp", ["2026-03-01T11:30", "20261301113000", "2026030111300", "202603011130000", ""]
)
def test_a_bad_publication_time_is_dropped_and_counted(stamp: str) -> None:
    issues: Counter[str] = Counter()
    extras = (
        f"<PAGE_PRECISEPUBTIMESTAMP>{stamp}</PAGE_PRECISEPUBTIMESTAMP><PAGE_TITLE>T</PAGE_TITLE>"
    )
    assert parse_line(make_row(extras=extras), issues).published_at is None
    assert issues == {Issue.PUBLISHED_AT_INVALID: 1}


@pytest.mark.parametrize(
    "tone",
    [
        "",
        "1,2,3,4,5,6",
        "1,2,3,4,5,6,7,8",
        "1,2,3,x,5,6,7",
        "1,2,3,nan,5,6,7",
        "1,2,3,inf,5,6,7",
        "1,2,3,1_0,5,6,7",
    ],
)
def test_a_bad_tone_is_dropped_and_counted(tone: str) -> None:
    issues: Counter[str] = Counter()
    assert parse_line(make_row(tone=tone), issues).tone is None
    assert issues == {Issue.TONE_MALFORMED: 1}


def test_themes_are_unique_in_file_order_and_bad_entries_are_counted() -> None:
    issues: Counter[str] = Counter()
    row = parse_line(
        make_row(
            themes=(
                "WB_137_WATER,9;TAX_FNCACT_MAYOR,12;NO_OFFSET;WB_137_WATER,x9;"
                "WB_137_WATER,40;bad name,3"
            )
        ),
        issues,
    )
    assert row.themes == ("WB_137_WATER", "TAX_FNCACT_MAYOR")
    assert issues == {Issue.THEME_MALFORMED: 3}
    assert parse_line(make_row(themes="")).themes == ()


def test_malformed_locations_are_counted() -> None:
    issues: Counter[str] = Counter()
    row = parse_line(
        make_row(locations="0#Georgia, , Georgia#GG#GG##42#.5#1#GG#51;1#France#FR#FR##46#2#FR#301"),
        issues,
    )
    assert len(row.locations) == 1 and row.primary is not None and row.primary.country == "FR"
    assert issues == {Issue.LOCATION_MALFORMED: 1}


def test_a_centroid_demotion_is_counted() -> None:
    issues: Counter[str] = Counter()
    row = parse_line(
        make_row(locations=CENTROID_AS_CITY),
        issues,
    )
    assert row.primary is not None and row.primary.demoted and not row.primary.is_point
    assert issues == {Issue.CENTROID_DEMOTED: 1}


@pytest.mark.parametrize("url", ["javascript:alert(1)", "ftp://files.example/a", "not a url", ""])
def test_an_identifier_that_is_not_an_http_link_gives_no_url(url: str) -> None:
    issues: Counter[str] = Counter()
    assert parse_line(make_row(url=url), issues).url is None
    assert issues == {Issue.URL_REJECTED: 1}


def test_language_cases() -> None:
    issues: Counter[str] = Counter()
    unknown = parse_line(
        make_row(record_id="20260301120000-T1", translation_info="srclc:zzz;eng:GT-ZZZ 1.0"), issues
    )
    assert unknown.lang is None and unknown.srclc == "zzz"
    assert issues == {Issue.SRCLC_UNKNOWN: 1}

    issues.clear()
    missing = parse_line(make_row(record_id="20260301120000-T2", translation_info=""), issues)
    assert missing.lang is None and missing.srclc is None
    assert issues == {Issue.TRANSLATION_INFO_MISSING: 1}

    issues.clear()
    odd = parse_line(
        make_row(record_id="20260301120000-T3", translation_info="eng:GT-XXX 1.0"), issues
    )
    assert odd.lang is None and odd.srclc is None
    assert issues == {Issue.TRANSLATION_INFO_MALFORMED: 1}

    issues.clear()
    english_with_code = parse_line(make_row(translation_info="srclc:deu;eng:GT-DEU 1.0"), issues)
    assert english_with_code.lang is not None and english_with_code.lang.tag == "de"
    assert not issues


def test_outlet_and_translation_info_are_sanitized() -> None:
    row = parse_line(
        make_row(
            outlet="harbor\u202e-gazette.example\u200b",
            record_id="20260301120000-T4",
            translation_info="srclc:fra;eng:\u202eGT",
        )
    )
    assert row.outlet == "harbor-gazette.example"
    assert row.translation_info == "srclc:fra;eng:GT"


def test_parse_gkg_counts_rows_blanks_and_quarantine() -> None:
    good = make_row()
    other = make_row(record_id="20260301120000-43")
    short = b"\t".join(good.split(b"\t")[:26])
    data = b"\n".join([good, short, b"", b"continuation of a broken record", other]) + b"\n"
    result = parse_gkg(data)
    assert [row.seq for row in result.rows] == [42, 43]
    assert [(q.line_no, q.reason, q.raw) for q in result.quarantined] == [
        (2, Reason.COLUMN_COUNT, short),
        (4, Reason.COLUMN_COUNT, b"continuation of a broken record"),
    ]
    stats = result.stats
    assert (stats.lines, stats.rows, stats.blank_lines) == (5, 2, 1)
    assert stats.quarantined == {Reason.COLUMN_COUNT: 2}
    assert stats.malformed_share == pytest.approx(2 / 4)


def test_a_file_without_a_final_newline_and_an_empty_file() -> None:
    assert len(parse_gkg(make_row()).rows) == 1
    empty = parse_gkg(b"")
    assert (empty.rows, empty.quarantined, empty.stats.lines, empty.stats.malformed_share) == (
        [],
        [],
        0,
        0.0,
    )


def test_broken_records_are_not_stitched_back_together() -> None:
    head = make_row(extras="<PAGE_LINKS>https://valley-dispatch.test/a")
    tail = b"https://valley-dispatch.test/b</PAGE_LINKS><PAGE_TITLE>Lost headline</PAGE_TITLE>"
    result = parse_gkg(head + b"\n\n" + tail + b"\n")
    assert len(result.rows) == 1 and result.rows[0].title is None
    assert [q.reason for q in result.quarantined] == [Reason.COLUMN_COUNT]
    assert result.stats.issues == {Issue.TITLE_MISSING: 1}
    assert result.stats.blank_lines == 1


def test_unknown_codes_are_tallied_per_code() -> None:
    rows = [
        make_row(record_id=f"20260301120000-T{i}", translation_info=f"srclc:{code};eng:x")
        for i, code in enumerate(["zzz", "zzz", "qqq", "fra"])
    ]
    stats = parse_gkg(b"\n".join(rows)).stats
    assert stats.unknown_srclc == {"zzz": 2, "qqq": 1}
    assert stats.issues == {Issue.SRCLC_UNKNOWN: 3}
