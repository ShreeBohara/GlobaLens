"""Writes the golden GKG fixtures in this folder.

Run from the repository root:

    uv run --no-sync python packages/gdelt/tests/golden/build_fixtures.py             # *.tsv
    uv run --no-sync python packages/gdelt/tests/golden/build_fixtures.py --expected  # and *.json

Every fixture has the shape of real GKG 2.1 rows: 27 tab-separated columns, non-ASCII title
characters written as upper-case hex references the way GDELT writes them, the same tags in the
extras column, the same broken-line and broken-byte patterns that were found in real files. The
content is invented. Titles are synthetic, and so are URLs and outlet names (design note Q27):
they use the reserved `.example` and `.test` domains. Place names, country codes and theme names
are GDELT's own vocabulary, not a publisher's text. No real headline is in this folder.

`--expected` writes what the parser returns today. Read the diff before committing it: the JSON
files are the reviewed record of what each fixture must parse to.
"""

import json
import sys
import unicodedata
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent

STAMP = "20260301120000"
TONE = (
    "-2.41545893719807,1.93236714975845,4.34782608695652,6.28019323671498,"
    "21.256038647343,0.483091787439614,186"
)
GCAM = "wc:186,c1.2:3,c12.1:9,c12.10:14,c12.12:4,v19.1:5.8125,v19.2:5.24,v20.1:0.5"

LYON = "4#Lyon, Rhone-Alpes, France#FR#FRB9#69#45.75#4.85#-1445171#58"
FRANCE = "1#France#FR#FR##46#2#FR#301"
AUSTIN = "3#Austin, Texas, United States#US#USTX#TX453#30.2672#-97.7431#1384879#77"
TEXAS = "2#Texas, United States#US#USTX##31.106#-97.6475#TX#120"
UNITED_STATES = "1#United States#US#US##39.828175#-98.5795#US#410"  # the Kansas centroid


def gdelt_escape(text: str) -> str:
    """Write non-ASCII characters as GDELT does: `&#x` + upper-case hex + `;`."""
    return "".join(ch if ord(ch) < 0x80 else f"&#x{ord(ch):X};" for ch in text)


def extras(
    title: str | None,
    *,
    published: str | None = None,
    links: str | None = None,
    authors: str | None = None,
    amp: str | None = None,
    escape: bool = True,
) -> str:
    parts: list[str] = []
    if links is not None:
        parts.append(f"<PAGE_LINKS>{links}</PAGE_LINKS>")
    if authors is not None:
        parts.append(f"<PAGE_AUTHORS>{authors}</PAGE_AUTHORS>")
    if published is not None:
        parts.append(f"<PAGE_PRECISEPUBTIMESTAMP>{published}</PAGE_PRECISEPUBTIMESTAMP>")
    if amp is not None:
        parts.append(f"<PAGE_ALTURL_AMP>{amp}</PAGE_ALTURL_AMP>")
    if title is not None:
        parts.append(f"<PAGE_TITLE>{gdelt_escape(title) if escape else title}</PAGE_TITLE>")
    return "".join(parts)


def row(
    seq: int,
    outlet: str,
    url: str,
    extras_xml: str | bytes,
    *,
    translated: str | None = None,
    themes: str = "",
    locations: str | bytes = "",
    tone: str = TONE,
    record_id: str | None = None,
    date: str = STAMP,
    collection: str = "1",
    translation_info: str | None = None,
    gcam: str | bytes = GCAM,
) -> bytes:
    """One GKG row. `translated` is the source-language code of a translated-stream row."""
    if record_id is None:
        record_id = f"{STAMP}-{'T' if translated is not None else ''}{seq}"
    if translation_info is None:
        translation_info = (
            f"srclc:{translated};eng:GT-{translated.upper()} 1.0" if translated is not None else ""
        )
    v2_locations = locations if isinstance(locations, bytes) else locations.encode()
    v1_locations = b";".join(
        b"#".join(entry.split(b"#")[:4] + entry.split(b"#")[5:8])
        for entry in v2_locations.split(b";")
        if entry.count(b"#") == 8
    )
    v1_themes = ";".join(dict.fromkeys(t.split(",")[0] for t in themes.split(";") if t))
    columns: list[bytes] = [
        record_id.encode(),
        date.encode(),
        collection.encode(),
        outlet.encode(),
        url.encode(),
        b"",  # V1COUNTS
        b"",  # V2.1COUNTS
        v1_themes.encode(),  # V1THEMES
        themes.encode(),  # V2ENHANCEDTHEMES
        v1_locations,  # V1LOCATIONS
        v2_locations,  # V2ENHANCEDLOCATIONS
        b"jane example;john sample",  # V1PERSONS
        b"Jane Example,45;John Sample,310",  # V2ENHANCEDPERSONS
        b"example river authority",  # V1ORGANIZATIONS
        b"Example River Authority,120",  # V2ENHANCEDORGANIZATIONS
        tone.encode(),  # V1.5TONE
        b"",  # V2.1ENHANCEDDATES
        gcam if isinstance(gcam, bytes) else gcam.encode(),  # V2GCAM
        f"https://img.{outlet}/photo.jpg".encode(),  # V2.1SHARINGIMAGE
        b"",  # V2.1RELATEDIMAGES
        b"",  # V2.1SOCIALIMAGEEMBEDS
        b"",  # V2.1SOCIALVIDEOEMBEDS
        b"",  # V2.1QUOTATIONS
        b"Jane Example,45;Example River Authority,120",  # V2.1ALLNAMES
        b"3,days of rain,96;",  # V2.1AMOUNTS
        translation_info.encode(),  # V2.1TRANSLATIONINFO
        extras_xml if isinstance(extras_xml, bytes) else extras_xml.encode(),  # V2EXTRASXML
    ]
    assert len(columns) == 27
    return b"\t".join(columns)


def lines(*rows: bytes) -> bytes:
    return b"".join(r + b"\n" for r in rows)


def english_basic() -> bytes:
    gazette = "harbor-gazette.example"
    return lines(
        row(
            0,
            gazette,
            f"https://www.{gazette}/world/2026/03/river-levels-rise",
            extras(
                "River levels rise in the northern valley after a week of rain",
                published="20260301113000",
                links=f"https://www.{gazette}/weather;https://www.{gazette}/valley",
                authors="Jane Example",
            ),
            themes="NATURAL_DISASTER_FLOOD,45;TAX_FNCACT_MAYOR,210;NATURAL_DISASTER_FLOOD,388;WB_137_WATER,402;",
            locations=f"{LYON};{FRANCE}",
        ),
        row(
            1,
            gazette,
            f"https://www.{gazette}/local/tide-gauges-budget",
            extras("Harbor council approves R&D budget for tide gauges"),
            themes="EPU_POLICY_BUDGET,30;TAX_FNCACT_COUNCIL,12;",
            locations=f"{AUSTIN};{TEXAS};{UNITED_STATES}",
        ),
        row(
            2,
            "northern-courier.example",
            "https://northern-courier.example/opinion/ferry-timetable/",
            extras("Opinion: why the ferry timetable matters", authors="John Sample"),
        ),
    )


def translated_entities() -> bytes:
    lantern = "daily-lantern.example"
    return lines(
        row(
            3,
            lantern,
            f"https://www.{lantern}/zh/river-1",
            extras("测试标题：北方山谷河水上涨", published="20260301101500"),
            translated="zho",
            locations="4#Wuhan, Hubei, China#CH#CH12#13121#30.5833#114.267#-1930776#22",
        ),
        row(
            14,
            lantern,
            f"https://www.{lantern}/ru/river-2",
            extras("Тестовый заголовок: уровень воды в реке растёт"),
            translated="rus",
            translation_info="srclc:rus;eng:Moses 2.1.1 / MosesCore Europarl ru-en / GT-RUS 1.0",
        ),
        row(
            205,
            lantern,
            f"https://www.{lantern}/ar/river-3",
            extras("عنوان تجريبي: ارتفاع منسوب النهر في الوادي الشمالي"),
            translated="ara",
        ),
        row(
            1206,
            lantern,
            f"https://www.{lantern}/es/rio-4",
            extras("Titular de prueba: «el río crece» – informe nº 4"),
            translated="spa",
        ),
        row(
            1207,
            lantern,
            f"https://www.{lantern}/ja/kawa-5",
            extras("テスト見出し：２０２６年の川の水位（ﾃｽﾄ）"),
            translated="jpn",
        ),
        # A decimal reference, a named reference with its semicolon, a bare ampersand and a
        # legacy name without a semicolon. Only the first two are references.
        row(
            1208,
            lantern,
            f"https://www.{lantern}/de/fragen-6",
            extras(
                "Q&amp;A: the mayor&#8217;s plan for R&D and &copy rules &lt;draft&gt;",
                escape=False,
            ),
            translated="deu",
        ),
    )


def malformed_column_counts() -> bytes:
    courier = "northern-courier.example"
    good_a = row(0, courier, f"https://{courier}/a", extras("First synthetic headline"))
    good_b = row(7, courier, f"https://{courier}/b", extras("Last synthetic headline"))
    twenty_six = b"\t".join(row(1, courier, f"https://{courier}/c", extras("x")).split(b"\t")[:26])
    twenty_eight = row(2, courier, f"https://{courier}/d", extras("x")) + b"\textra column"
    return lines(
        good_a,
        twenty_six,
        twenty_eight,
        b"this line is not a GKG row",
        row(3, courier, f"https://{courier}/e", extras("x"), record_id="not-a-record-id"),
        row(4, courier, f"https://{courier}/f", extras("x"), date="2026030112"),
        row(5, courier, f"https://{courier}/g", extras("x"), date="20261301120000"),
        row(6, courier, f"https://{courier}/h", extras("x"), record_id=f"{STAMP}-T"),
        good_b,
    )


def broken_record_newlines() -> bytes:
    """A record whose PAGE_LINKS holds line breaks, as real translated files have them: the head
    keeps 27 columns and loses its title; a blank line and three one-column lines follow."""
    dispatch = "valley-dispatch.test"
    head = row(
        11,
        dispatch,
        f"https://www.{dispatch}/noticias/cortado",
        f"<PAGE_LINKS>https://www.{dispatch}/a;https://www.{dispatch}/b",
        translated="por",
    )
    return lines(
        row(
            10,
            dispatch,
            f"https://www.{dispatch}/noticias/antes",
            extras("Título de teste: antes"),
            translated="por",
        ),
        head,
        b"",
        f"https://www.{dispatch}/c".encode(),
        f"https://www.{dispatch}/d;https://www.{dispatch}/e".encode(),
        (
            f"https://www.{dispatch}/f</PAGE_LINKS>"
            "<PAGE_TITLE>T&#xED;tulo perdido numa quebra de linha</PAGE_TITLE>"
        ).encode(),
        row(
            12,
            dispatch,
            f"https://www.{dispatch}/noticias/depois",
            extras("Título de teste: depois"),
            translated="por",
        ),
    )


def broken_utf8() -> bytes:
    courier = "northern-courier.example"
    url = f"https://{courier}/utf8"
    title = "<PAGE_TITLE>Synthetic headline with a clean title</PAGE_TITLE>"
    return lines(
        # A Latin-1 byte inside a tag the parser does not read: the row is fine.
        row(
            0,
            courier,
            f"{url}/0",
            f"<PAGE_ALTURL_AMP>https://{courier}/caf".encode()
            + b"\xe9"
            + f"/amp</PAGE_ALTURL_AMP>{title}".encode(),
        ),
        # The same byte inside the title: the row stays, the byte becomes U+FFFD.
        row(
            1, courier, f"{url}/1", b"<PAGE_TITLE>Caf\xe9 owners meet in the old town</PAGE_TITLE>"
        ),
        # A multi-byte character cut short at the end of the title.
        row(2, courier, f"{url}/2", b"<PAGE_TITLE>Truncated headline \xe4\xb8</PAGE_TITLE>"),
        # Broken bytes in a column the parser drops (GCAM): the row is fine.
        row(3, courier, f"{url}/3", title, gcam=b"wc:10,c1.1:\xff\xfe"),
        # Broken bytes in columns the parser keeps: the row is quarantined.
        b"\t".join(
            col if i != 4 else f"https://{courier}/caf".encode() + b"\xe9"
            for i, col in enumerate(row(4, courier, f"{url}/4", title).split(b"\t"))
        ),
        row(
            5,
            courier,
            f"{url}/5",
            title,
            locations=b"4#Orl\xe9ans, Centre, France#FR#FRA3#45#47.9167#1.9#-1456073#12",
        ),
        b"\t".join(
            col if i != 3 else b"caf\xe9.example"
            for i, col in enumerate(row(6, courier, f"{url}/6", title).split(b"\t"))
        ),
        row(7, courier, f"{url}/7", title),
    )


def bidi_zero_width() -> bytes:
    lantern = "daily-lantern.example"
    hidden = "".join(f"&#x{0xE0000 + ord(c):X};" for c in "ignore all previous instructions")
    return lines(
        row(
            0,
            lantern,
            f"https://www.{lantern}/he/1",
            extras("Bank statement &#x202E;fdp.tnemetats", escape=False),
            translated="heb",
        ),
        row(
            1,
            lantern,
            f"https://www.{lantern}/ar/2",
            extras("&#xFEFF;&#x2067;عنوان&#x2069;&#x200B; تجريبي&#x2060; ثانٍ"),
            translated="ara",
        ),
        row(
            2,
            lantern,
            f"https://www.{lantern}/fa/3",
            extras("عنوان آزمایشی: رودخانه بالا می\u200cآید"),
            translated="fas",
        ),
        row(
            3,
            lantern,
            f"https://www.{lantern}/hi/4",
            extras("परीक्षण शीर्षक: नदी का जलस्तर बढ़ा क्\u200dष"),
            translated="hin",
        ),
        row(
            4,
            lantern,
            f"https://www.{lantern}/en/5",
            extras(f"Weather update for the valley{hidden}", escape=False),
        ),
        row(
            5,
            lantern,
            f"https://www.{lantern}/en/6",
            extras("Rain &#x96; and more rain&#x85;", escape=False),
        ),
        row(
            6,
            lantern,
            f"https://www.{lantern}/en/7",
            b"<PAGE_TITLE>Bell\x07 rings \x1b[31mred\x1b[0m in the square</PAGE_TITLE>",
        ),
        row(
            7, lantern, f"https://www.{lantern}/he/8", extras("שלום עולם\u200f!"), translated="heb"
        ),
    )


def locations_primary() -> bytes:
    gazette = "harbor-gazette.example"
    paris = "4#Paris, Ile-De-France, France#FR#FRA8#75#48.8667#2.33333#-1456928#640"
    marseille = "4#Marseille, Provence-Alpes-Cote D'azur, France#FR#FRB8#13#43.3#5.4#-1449947#95"
    germany = "1#Germany#GM#GM##51#9#GM#20"
    bavaria = "5#Bayern, Germany#GM#GM02##49#11.5#-1746443#200"
    ohio = "2#Ohio, United States#US#USOH##40.3736#-82.7755#OH#150"
    japan = "1#Japan#JA#JA##36#138#JA#44"
    brazil = "1#Brazil#BR#BR##-10#-55#BR#18"
    dallas = "3#Dallas, Texas, United States#US#USTX#TX113#32.7831#-96.8067#1380944#77"

    def r(seq: int, locs: str) -> bytes:
        return row(
            seq,
            gazette,
            f"https://www.{gazette}/geo/{seq}",
            extras(f"Synthetic location case {seq}"),
            locations=locs,
        )

    return lines(
        r(0, f"1#France#FR#FR##46#2#FR#12;{paris};{marseille}"),  # earliest city by offset
        r(1, f"{germany};{bavaria}"),  # ADM1 with a numeric FeatureID is an area, not a point
        r(2, f"1#United States#US#US##39.828175#-98.5795#US#5;{ohio}"),  # US state beats country
        r(3, f"{japan};{brazil}"),  # earliest country
        r(4, ""),  # no location
        r(5, f"{AUSTIN};{dallas}"),  # same offset: the first in the column
        r(6, f"{TEXAS};5#Ontario, Canada#CA#CA08##50#-85#-570406#90"),  # earliest ADM1-level area
        r(7, f"{bavaria};{germany};{LYON}"),  # a city beats every area, wherever it is listed
    )


def centroid_blocklist() -> bytes:
    courier = "northern-courier.example"
    planted = "3#Somewhere, Kansas, United States#US#USKS#KS000#39.828175#-98.5795#999999#10"
    planted_world = "4#Somewhere, United States#US#US00##39.828175#-98.5795#-999999#10"
    wichita = "3#Wichita, Kansas, United States#US#USKS#KS173#37.6922#-97.3375#473862#500"
    kansas = "2#Kansas, United States#US#USKS##38.5111#-96.8005#KS#700"

    def r(seq: int, locs: str) -> bytes:
        return row(
            seq,
            courier,
            f"https://{courier}/centroid/{seq}",
            extras(f"Synthetic centroid case {seq}"),
            locations=locs,
        )

    return lines(
        r(0, "1#United States#US#US##39.828175#-98.5795#US#33"),  # as real files have it
        r(1, planted),  # a city-level type on the centroid: counted as country-level
        r(2, f"{planted};{wichita}"),  # the real city later in the text is the primary location
        r(3, f"{planted_world};{kansas}"),  # an ADM1-level area is more specific than the centroid
    )


def odd_fields() -> bytes:
    gazette = "harbor-gazette.example"
    url = f"https://www.{gazette}/odd"
    plain = extras("Synthetic headline for an odd field")
    tbilisi = "4#Tbilisi, T'bilisi, Georgia#GG#GG51##41.725#44.7908#-2330649#80"
    return lines(
        # A ten-field entry of the shape real files carry, next to a good one.
        row(
            0,
            gazette,
            f"{url}/0",
            plain,
            locations=f"0#Georgia, , Georgia#GG#GG##42#.5#1#GG#51;{tbilisi}",
        ),
        # Latitude out of range; an offset that is not a number.
        row(
            1,
            gazette,
            f"{url}/1",
            plain,
            locations="4#Nowhere#XX#XX00##95.5#10#-1#20;4#Elsewhere#XX#XX00##10#20#-2#abc",
        ),
        # A country without coordinates, as real files have it.
        row(2, gazette, f"{url}/2", plain, locations="1#Aruba#AA#AA####AA#15"),
        row(3, gazette, f"{url}/3", plain, tone="-2.4,1.9,4.3,6.2,21.2,0.4"),
        row(4, gazette, f"{url}/4", plain, tone="-2.4,1.9,4.3,six,21.2,0.4,186"),
        row(
            5,
            gazette,
            f"{url}/5",
            plain,
            themes="TAX_FNCACT_MAYOR,12;BROKEN_NO_OFFSET;WB_137_WATER,x9;ENV_CLIMATECHANGE,40;",
        ),
        row(
            6,
            gazette,
            f"{url}/6",
            extras("Synthetic headline with a dashed timestamp", published="2026-03-01T11:30"),
        ),
        row(
            7,
            gazette,
            f"{url}/7",
            extras("Synthetic headline with month thirteen", published="20261301113000"),
        ),
        row(8, gazette, f"{url}/8", extras("")),
        row(9, gazette, f"{url}/9", extras(None, authors="Jane Example")),
        row(10, gazette, f"{url}/10", extras("  &#x200B;&#xFEFF; ", escape=False)),
        # A city-level entry without coordinates cannot be a point and is not guessed into an area.
        row(11, gazette, f"{url}/11", plain, locations="4#Ghost Town, Nowhere#XX#XX00####-5#9"),
        row(12, gazette, f"{url}/12", "<PAGE_TITLE>Synthetic headline whose tag never closes"),
    )


def urls() -> bytes:
    lantern = "daily-lantern.example"
    plain = extras("Synthetic headline for a URL case")

    def r(seq: int, url: str, collection: str = "1") -> bytes:
        return row(seq, lantern, url, plain, collection=collection)

    return lines(
        r(0, f"https://www.{lantern}/story?id=71&utm_source=feed&utm_medium=rss&page=2"),
        r(1, f"http://{lantern}/a/?fbclid=AbC123"),
        r(2, "HTTPS://WWW.Daily-Lantern.EXAMPLE:443/Path/Case?Q=1"),
        r(3, f"https://{lantern}/a#comments"),
        r(4, f"ftp://files.{lantern}/a.txt"),
        r(5, "javascript:alert(1)"),
        r(6, "Example Journal of Rivers, vol. 3", collection="2"),
        r(7, f"https://{lantern}"),
        r(8, f"http://{lantern}:8080/a"),
        r(9, f"https://reader@{lantern}/a"),
        r(10, f"https://{lantern}/caf%C3%A9/r%c3%ado?q=a%20b"),
        r(11, f"https://{lantern}/a b"),
        r(12, f"https://{lantern}/río/测试"),
    )


def languages() -> bytes:
    lantern = "daily-lantern.example"

    def r(
        seq: int, code: str | None, info: str | None = None, *, translated_id: bool = True
    ) -> bytes:
        return row(
            seq,
            lantern,
            f"https://www.{lantern}/lang/{seq}",
            extras(f"Synthetic headline for language case {seq}"),
            translated=code,
            translation_info=info,
            record_id=f"{STAMP}-{'T' if translated_id else ''}{seq}",
        )

    return lines(
        r(0, "axe"),  # GDELT's code for Azerbaijani
        r(1, "fas"),
        r(2, "heb"),
        r(3, "urd"),
        r(4, "zho"),
        r(5, "zzz"),  # a code the table does not know
        r(6, None, ""),  # a translated row with no translation info
        r(7, None, translated_id=False),  # the English stream
        r(8, None, "eng:GT-XXX 1.0"),  # translation info without a source language
        r(9, "srp"),
    )


def long_title_and_whitespace() -> bytes:
    gazette = "harbor-gazette.example"
    courier = "northern-courier.example"
    long_title = "Synthetic long headline " + "about the river and the valley " * 20
    same = "Storm warning issued for the northern valley"
    return lines(
        row(0, gazette, f"https://www.{gazette}/long", extras(long_title)),
        row(
            1,
            gazette,
            f"https://www.{gazette}/spaces",
            extras("  Two  spaces   inside \u00a0 and around  "),
        ),
        row(2, gazette, f"https://www.{gazette}/same", extras(same)),
        row(3, courier, f"https://{courier}/same", extras(same)),
        # The same headline with a zero-width space, a no-break space and fullwidth letters.
        row(
            4,
            courier,
            f"https://{courier}/same-hidden",
            extras("Storm\u200b warning\u00a0issued for the ｎｏｒｔｈｅｒｎ valley"),
        ),
        row(
            5,
            courier,
            f"https://{courier}/different",
            extras("Storm warning lifted for the northern valley"),
        ),
    )


FIXTURES = {
    "01_english_basic": english_basic,
    "02_translated_entities": translated_entities,
    "03_malformed_column_counts": malformed_column_counts,
    "04_broken_record_newlines": broken_record_newlines,
    "05_broken_utf8": broken_utf8,
    "06_bidi_zero_width": bidi_zero_width,
    "07_locations_primary": locations_primary,
    "08_centroid_blocklist": centroid_blocklist,
    "09_odd_fields": odd_fields,
    "10_urls": urls,
    "11_languages": languages,
    "12_long_title_and_whitespace": long_title_and_whitespace,
}


def expected_json(data: bytes) -> dict[str, Any]:
    from gdelt import parse_gkg, result_to_json

    return result_to_json(parse_gkg(data))


def escape_hidden(json_text: str) -> str:
    """Write characters nobody can see in a diff (format and control characters, odd spaces,
    U+FFFD) as JSON escapes. Everything else stays readable."""

    def escaped(ch: str) -> str:
        code = ord(ch)
        if code < 0x10000:
            return f"\\u{code:04x}"
        code -= 0x10000
        return f"\\u{0xD800 + (code >> 10):04x}\\u{0xDC00 + (code & 0x3FF):04x}"

    def hidden(ch: str) -> bool:
        if ch == "\n" or " " <= ch <= "~":
            return False
        category = unicodedata.category(ch)
        return (
            category in ("Cc", "Cf", "Cs", "Co", "Cn", "Zl", "Zp", "Zs")
            or ord(ch) == 0xFFFD
            or 0xFE00 <= ord(ch) <= 0xFE0F
        )

    return "".join(escaped(ch) if hidden(ch) else ch for ch in json_text)


def main(argv: list[str]) -> int:
    write_expected = "--expected" in argv
    for name, build in FIXTURES.items():
        data = build()
        (HERE / f"{name}.tsv").write_bytes(data)
        if write_expected:
            text = json.dumps(expected_json(data), ensure_ascii=False, indent=2) + "\n"
            (HERE / f"{name}.json").write_text(escape_hidden(text), encoding="utf-8")
    print(f"wrote {len(FIXTURES)} fixtures to {HERE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
