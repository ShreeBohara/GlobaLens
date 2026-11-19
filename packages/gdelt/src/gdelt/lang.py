"""GDELT's source-language codes: BCP 47 tag, endonym, direction and script.

A translated GKG row names its source language in `TranslationInfo` as `srclc:<code>`. The
codes look like ISO 639-3 but are GDELT's own: Azerbaijani is `axe`, not `aze`. The English
stream has no `TranslationInfo`; its language is the first row of the table, `eng`.

`LANGS` is ordered, and the order is a wire format: a point shard stores a language as its
index in this table. New languages are appended. Reordering or removing a row needs a new
`LANG_TABLE_VERSION`.

Where the values come from:

- The codes: every `srclc` value in three days of real files (both streams, 12-14 November
  2026) is here. `amh` and `bod` were not in those days; they are in the table because GDELT
  lists Amharic and Tibetan among the languages it translates.
- Tag, endonym, direction, script: CLDR 48, read through ICU 78.3 (`Intl.DisplayNames`,
  `Intl.Locale`). Endonyms start with a capital where the script has one, as in a language
  menu. Two choices differ from CLDR's likely script: `zho` is `Hani`, because the stream
  carries Simplified and Traditional text under one code, and CLDR would say `Hans`; and the
  script of a language written in two (`srp`: Cyrillic and Latin) is only the likelier one.
  A title's own characters decide which font draws it.

A code that is not in the table is never guessed at: `from_srclc` returns None, the parser
counts it, and `gdelt.srclc_check` fails on it.
"""

import re
from dataclasses import dataclass
from typing import Literal

__all__ = ["ENGLISH", "LANGS", "LANG_TABLE_VERSION", "Lang", "from_srclc", "srclc_of"]

LANG_TABLE_VERSION = 1


@dataclass(frozen=True, slots=True)
class Lang:
    """One row of the language table."""

    index: int  # position in LANGS
    code: str  # GDELT's code
    tag: str  # BCP 47
    endonym: str  # the language's name in the language
    direction: Literal["ltr", "rtl"]
    script: str  # ISO 15924, the likely script


_ROWS: tuple[tuple[str, str, str, Literal["ltr", "rtl"], str], ...] = (
    ("eng", "en", "English", "ltr", "Latn"),
    ("afr", "af", "Afrikaans", "ltr", "Latn"),
    ("amh", "am", "አማርኛ", "ltr", "Ethi"),
    ("ara", "ar", "العربية", "rtl", "Arab"),
    ("axe", "az", "Azərbaycan", "ltr", "Latn"),
    ("ben", "bn", "বাংলা", "ltr", "Beng"),
    ("bod", "bo", "བོད་སྐད་", "ltr", "Tibt"),
    ("bos", "bs", "Bosanski", "ltr", "Latn"),
    ("bul", "bg", "Български", "ltr", "Cyrl"),
    ("cat", "ca", "Català", "ltr", "Latn"),
    ("ces", "cs", "Čeština", "ltr", "Latn"),
    ("dan", "da", "Dansk", "ltr", "Latn"),
    ("deu", "de", "Deutsch", "ltr", "Latn"),
    ("ell", "el", "Ελληνικά", "ltr", "Grek"),
    ("est", "et", "Eesti", "ltr", "Latn"),
    ("fas", "fa", "فارسی", "rtl", "Arab"),
    ("fin", "fi", "Suomi", "ltr", "Latn"),
    ("fra", "fr", "Français", "ltr", "Latn"),
    ("glg", "gl", "Galego", "ltr", "Latn"),
    ("guj", "gu", "ગુજરાતી", "ltr", "Gujr"),
    ("heb", "he", "עברית", "rtl", "Hebr"),
    ("hin", "hi", "हिन्दी", "ltr", "Deva"),
    ("hrv", "hr", "Hrvatski", "ltr", "Latn"),
    ("hun", "hu", "Magyar", "ltr", "Latn"),
    ("hye", "hy", "Հայերեն", "ltr", "Armn"),
    ("ind", "id", "Indonesia", "ltr", "Latn"),
    ("isl", "is", "Íslenska", "ltr", "Latn"),
    ("ita", "it", "Italiano", "ltr", "Latn"),
    ("jpn", "ja", "日本語", "ltr", "Jpan"),
    ("kan", "kn", "ಕನ್ನಡ", "ltr", "Knda"),
    ("kat", "ka", "ქართული", "ltr", "Geor"),
    ("kaz", "kk", "Қазақ тілі", "ltr", "Cyrl"),
    ("kor", "ko", "한국어", "ltr", "Kore"),
    ("lav", "lv", "Latviešu", "ltr", "Latn"),
    ("lit", "lt", "Lietuvių", "ltr", "Latn"),
    ("mal", "ml", "മലയാളം", "ltr", "Mlym"),
    ("mar", "mr", "मराठी", "ltr", "Deva"),
    ("mkd", "mk", "Македонски", "ltr", "Cyrl"),
    ("mon", "mn", "Монгол", "ltr", "Cyrl"),
    ("msa", "ms", "Melayu", "ltr", "Latn"),
    ("nep", "ne", "नेपाली", "ltr", "Deva"),
    ("nld", "nl", "Nederlands", "ltr", "Latn"),
    ("nno", "nn", "Norsk nynorsk", "ltr", "Latn"),
    ("nor", "no", "Norsk", "ltr", "Latn"),
    ("pan", "pa", "ਪੰਜਾਬੀ", "ltr", "Guru"),
    ("pol", "pl", "Polski", "ltr", "Latn"),
    ("por", "pt", "Português", "ltr", "Latn"),
    ("ron", "ro", "Română", "ltr", "Latn"),
    ("rus", "ru", "Русский", "ltr", "Cyrl"),
    ("sin", "si", "සිංහල", "ltr", "Sinh"),
    ("slk", "sk", "Slovenčina", "ltr", "Latn"),
    ("slv", "sl", "Slovenščina", "ltr", "Latn"),
    ("som", "so", "Soomaali", "ltr", "Latn"),
    ("spa", "es", "Español", "ltr", "Latn"),
    ("sqi", "sq", "Shqip", "ltr", "Latn"),
    ("srp", "sr", "Српски", "ltr", "Cyrl"),
    ("swa", "sw", "Kiswahili", "ltr", "Latn"),
    ("swe", "sv", "Svenska", "ltr", "Latn"),
    ("tam", "ta", "தமிழ்", "ltr", "Taml"),
    ("tel", "te", "తెలుగు", "ltr", "Telu"),
    ("tha", "th", "ไทย", "ltr", "Thai"),
    ("tur", "tr", "Türkçe", "ltr", "Latn"),
    ("ukr", "uk", "Українська", "ltr", "Cyrl"),
    ("urd", "ur", "اردو", "rtl", "Arab"),
    ("vie", "vi", "Tiếng Việt", "ltr", "Latn"),
    ("zho", "zh", "中文", "ltr", "Hani"),
)

LANGS: tuple[Lang, ...] = tuple(Lang(index, *row) for index, row in enumerate(_ROWS))
"""The language table. A language's index in it is what the point shards store."""

ENGLISH = LANGS[0]
"""The language of the English stream."""

_BY_CODE = {lang.code: lang for lang in LANGS}
_SRCLC = re.compile(r"srclc:([A-Za-z]{1,8})(?:;|$)")


def from_srclc(code: str) -> Lang | None:
    """The table row for one of GDELT's source-language codes, or None for an unknown code."""
    return _BY_CODE.get(code)


def srclc_of(translation_info: str) -> str | None:
    """The source-language code in a `TranslationInfo` column, or None if it has none."""
    match = _SRCLC.match(translation_info)
    return match.group(1) if match else None
