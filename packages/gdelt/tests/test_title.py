"""Title cleaning: entity decoding, sanitizing, NFKC and the title hash."""

import hashlib
import html

import pytest
from gdelt import clean_title, decode_entities, title_hash


def test_decodes_hex_references_the_way_gdelt_writes_them() -> None:
    assert decode_entities("&#x6D4B;&#x8BD5;&#x6807;&#x9898;") == "测试标题"
    assert decode_entities("caf&#xE9; r&#xED;o") == "café río"


def test_decodes_decimal_and_named_references_that_end_in_a_semicolon() -> None:
    assert decode_entities("the mayor&#8217;s plan") == "the mayor’s plan"
    assert decode_entities("Q&amp;A &lt;draft&gt; &quot;x&quot;") == 'Q&A <draft> "x"'
    assert decode_entities("a&nbsp;b") == "a\u00a0b"


@pytest.mark.parametrize(
    "text",
    [
        "R&D",
        "AT&T",
        "Q&A",
        "&copy rules",
        "this &amp that",
        "&#x4E2D",
        "&#20013",
        "&notanentity;",
        "&;",
        "& #x41;",
    ],
)
def test_leaves_everything_else_alone(text: str) -> None:
    # GDELT writes a bare "&" as it is, so "&copy" or "&amp" without a semicolon is text.
    assert decode_entities(text) == text


def test_decodes_once_only() -> None:
    assert decode_entities("&amp;lt;b&amp;gt;") == "&lt;b&gt;"
    assert decode_entities("&#x26;#x41;") == "&#x41;"


def test_numeric_references_follow_the_html_standard() -> None:
    """Same result as html.unescape for every kind of code point: the C1 range that browsers
    read as Windows-1252, surrogates, out-of-range values and noncharacters included."""
    code_points = [
        *range(0x0, 0x120),
        *range(0xD7F0, 0xE010),
        *range(0xFDC0, 0xFE00),
        *range(0xFFF0, 0x10010),
        0x1FFFE,
        0x1FFFF,
        0x10FFFD,
        0x10FFFE,
        0x10FFFF,
        0x110000,
        0x7FFFFFFF,
        *range(0x100, 0x110000, 251),
    ]
    for cp in code_points:
        for ref in (f"&#x{cp:X};", f"&#x{cp:x};", f"&#{cp};", f"&#X{cp:X};"):
            assert decode_entities(ref) == html.unescape(ref), ref


def test_clean_title_decodes_sanitizes_and_normalizes() -> None:
    raw = "&#xFEFF;&#x6D4B;&#x8BD5;&#xFF1A;  &#x202E;ｆｕｌｌ&#x200B; width "
    assert clean_title(raw) == "测试: full width"


def test_clean_title_keeps_markup_as_text() -> None:
    assert clean_title("&lt;script&gt;alert(1)&lt;/script&gt;") == "<script>alert(1)</script>"


def test_clean_title_can_come_back_empty() -> None:
    assert clean_title("") == ""
    assert clean_title(" &#x200B;&#xFEFF; ") == ""


def test_title_hash_is_the_first_eight_bytes_of_sha256() -> None:
    title = "Storm warning issued for the northern valley"
    assert title_hash(title) == bytes.fromhex("b003c962cd5833d6")
    assert title_hash(title) == hashlib.sha256(title.encode("utf-8")).digest()[:8]
    assert len(title_hash("")) == 8


def test_copies_of_a_title_share_a_hash_after_cleaning() -> None:
    plain = clean_title("Storm warning issued for the northern valley")
    hidden = clean_title("Storm&#x200B; warning&#xA0;issued for the &#xFF4E;orthern valley")
    assert plain == hidden
    assert title_hash(plain) == title_hash(hidden)
    assert title_hash(plain) != title_hash(
        clean_title("Storm warning lifted for the northern valley")
    )
