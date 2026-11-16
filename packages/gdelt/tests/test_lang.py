"""The language table: GDELT's `srclc` codes to BCP 47 tag, endonym, direction and script."""

import re
import unicodedata

from gdelt import ENGLISH, LANG_TABLE_VERSION, LANGS, Lang, from_srclc

# The order is the wire format: a point shard stores a language as its index in this table.
# New languages are appended; nothing is reordered or removed without a new table version.
PINNED_ORDER = [
    "eng", "afr", "amh", "ara", "axe", "ben", "bod", "bos", "bul", "cat", "ces", "dan", "deu",
    "ell", "est", "fas", "fin", "fra", "glg", "guj", "heb", "hin", "hrv", "hun", "hye", "ind",
    "isl", "ita", "jpn", "kan", "kat", "kaz", "kor", "lav", "lit", "mal", "mar", "mkd", "mon",
    "msa", "nep", "nld", "nno", "nor", "pan", "pol", "por", "ron", "rus", "sin", "slk", "slv",
    "som", "spa", "sqi", "srp", "swa", "swe", "tam", "tel", "tha", "tur", "ukr", "urd", "vie",
    "zho",
]  # fmt: skip

RTL = {"ara", "fas", "heb", "urd"}


def test_the_table_version_and_order_are_pinned() -> None:
    assert LANG_TABLE_VERSION == 1
    assert [lang.code for lang in LANGS] == PINNED_ORDER
    assert [lang.index for lang in LANGS] == list(range(len(LANGS)))
    assert len(LANGS) <= 256, "the index must fit the point shard's uint8"


def test_the_english_stream_is_en_at_index_zero() -> None:
    assert ENGLISH is LANGS[0]
    assert (ENGLISH.code, ENGLISH.tag, ENGLISH.index, ENGLISH.direction) == ("eng", "en", 0, "ltr")


def test_gdelt_writes_azerbaijani_as_axe() -> None:
    azerbaijani = from_srclc("axe")
    assert azerbaijani is not None
    assert (azerbaijani.tag, azerbaijani.script, azerbaijani.direction) == ("az", "Latn", "ltr")
    assert from_srclc("aze") is None  # the ISO code has never been seen in the feed


def test_unknown_codes_are_none_not_a_guess() -> None:
    for code in ("", "zzz", "ENG", "en", "srclc:fra", "fr", "fra "):
        assert from_srclc(code) is None


def test_lookup_returns_the_table_row() -> None:
    for lang in LANGS:
        assert from_srclc(lang.code) is lang


def test_codes_and_tags_are_unique() -> None:
    assert len({lang.code for lang in LANGS}) == len(LANGS)
    assert len({lang.tag for lang in LANGS}) == len(LANGS)


def test_shapes_of_every_row() -> None:
    for lang in LANGS:
        assert isinstance(lang, Lang)
        assert re.fullmatch(r"[a-z]{3}", lang.code), lang
        assert re.fullmatch(r"[a-z]{2,3}", lang.tag), lang  # a bare language subtag
        assert re.fullmatch(r"[A-Z][a-z]{3}", lang.script), lang  # ISO 15924
        assert lang.direction in ("ltr", "rtl"), lang
        assert lang.endonym and lang.endonym == lang.endonym.strip(), lang
        assert unicodedata.is_normalized("NFC", lang.endonym), lang


def test_right_to_left_languages() -> None:
    assert {lang.code for lang in LANGS if lang.direction == "rtl"} == RTL
    for lang in LANGS:
        if lang.direction == "rtl":
            assert lang.script in ("Arab", "Hebr"), lang


def test_endonyms_are_written_in_the_language_s_own_script() -> None:
    expected_block = {
        "Arab": "ARABIC", "Armn": "ARMENIAN", "Beng": "BENGALI", "Cyrl": "CYRILLIC",
        "Deva": "DEVANAGARI", "Ethi": "ETHIOPIC", "Geor": "GEORGIAN", "Grek": "GREEK",
        "Gujr": "GUJARATI", "Guru": "GURMUKHI", "Kore": "HANGUL", "Hani": "CJK",
        "Hebr": "HEBREW", "Jpan": "CJK", "Knda": "KANNADA", "Latn": "LATIN",
        "Mlym": "MALAYALAM", "Sinh": "SINHALA", "Taml": "TAMIL",
        "Telu": "TELUGU", "Thai": "THAI", "Tibt": "TIBETAN",
    }  # fmt: skip
    for lang in LANGS:
        first_letter = next(ch for ch in lang.endonym if ch.isalpha())
        assert unicodedata.name(first_letter).startswith(expected_block[lang.script]), lang


def test_a_few_rows_in_full() -> None:
    chinese = from_srclc("zho")
    assert chinese is not None
    assert chinese == Lang(chinese.index, "zho", "zh", "中文", "ltr", "Hani")
    assert LANGS[chinese.index] is chinese
    arabic = from_srclc("ara")
    assert arabic is not None and (arabic.tag, arabic.endonym, arabic.script) == (
        "ar",
        "العربية",
        "Arab",
    )
    serbian = from_srclc("srp")
    assert serbian is not None and (serbian.tag, serbian.script) == ("sr", "Cyrl")
    norwegian = from_srclc("nor")
    nynorsk = from_srclc("nno")
    assert norwegian is not None and nynorsk is not None
    assert (norwegian.tag, nynorsk.tag) == ("no", "nn")
