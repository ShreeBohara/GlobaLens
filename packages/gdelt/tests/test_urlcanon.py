"""URL canonicalization: the result must still be the link a visitor opens."""

import pytest
from gdelt import canon_url

SITE = "daily-lantern.example"


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        # Already canonical: returned as it is.
        (
            f"https://www.{SITE}/world/2026/03/river-levels-rise",
            f"https://www.{SITE}/world/2026/03/river-levels-rise",
        ),
        (f"http://{SITE}/a/", f"http://{SITE}/a/"),
        # Scheme and host in lower case; the path keeps its case.
        ("HTTPS://WWW.Daily-Lantern.EXAMPLE/Path/Case?Q=1", f"https://www.{SITE}/Path/Case?Q=1"),
        # Default ports go; other ports stay.
        (f"https://{SITE}:443/a", f"https://{SITE}/a"),
        (f"http://{SITE}:80/a", f"http://{SITE}/a"),
        (f"http://{SITE}:8080/a", f"http://{SITE}:8080/a"),
        (f"https://{SITE}:80/a", f"https://{SITE}:80/a"),
        # An empty path is "/".
        (f"https://{SITE}", f"https://{SITE}/"),
        (f"https://{SITE}?id=1", f"https://{SITE}/?id=1"),
        # Fragments never reach the server.
        (f"https://{SITE}/a#comments", f"https://{SITE}/a"),
        (f"https://{SITE}/a?id=1#top", f"https://{SITE}/a?id=1"),
        # Tracking parameters go; the others keep their order and their exact text.
        (
            f"https://{SITE}/story?id=71&utm_source=feed&utm_medium=rss&page=2",
            f"https://{SITE}/story?id=71&page=2",
        ),
        (f"https://{SITE}/a/?fbclid=AbC123", f"https://{SITE}/a/"),
        (f"https://{SITE}/a?UTM_Source=x&gclid=1&b=2&a=1", f"https://{SITE}/a?b=2&a=1"),
        (
            f"https://{SITE}/a?q=a%20b&x=%C3%A9&empty=&flag",
            f"https://{SITE}/a?q=a%20b&x=%C3%A9&empty=&flag",
        ),
        (f"https://{SITE}/a?", f"https://{SITE}/a"),
        # Names that only look like trackers are content.
        (
            f"https://{SITE}/a?ref=42&reference=x&source=rss&utmost=1",
            f"https://{SITE}/a?ref=42&reference=x&source=rss&utmost=1",
        ),
        # User names are not part of a public link.
        (f"https://reader@{SITE}/a", f"https://{SITE}/a"),
        # Paths are left byte for byte: no case change in escapes, no slash added or removed.
        (f"https://{SITE}/caf%C3%A9/r%c3%ado", f"https://{SITE}/caf%C3%A9/r%c3%ado"),
        (f"https://{SITE}/río/测试", f"https://{SITE}/río/测试"),
        (f"https://www.{SITE}/amp/story/", f"https://www.{SITE}/amp/story/"),
        (f"http://m.{SITE}/story", f"http://m.{SITE}/story"),
    ],
)
def test_canonical_form(url: str, expected: str) -> None:
    assert canon_url(url) == expected
    assert canon_url(expected) == expected, "canon_url must be idempotent"


@pytest.mark.parametrize(
    "not_a_link",
    [
        "",
        "javascript:alert(1)",
        "data:text/html,<script>alert(1)</script>",
        f"ftp://files.{SITE}/a.txt",
        f"//{SITE}/a",
        f"{SITE}/a",
        "https://",
        "https:///path-without-host",
        f"https://{SITE}/a b",
        f"https://{SITE}/a\tb",
        f" https://{SITE}/a",
        f"https://{SITE}/a\n",
        f"https://{SITE}/a\x00",
        f"https://{SITE}:port/a",
        f"https://{SITE}:99999/a",
        "https://[not-an-ip]/a",
        "Example Journal of Rivers, vol. 3",
    ],
)
def test_anything_that_is_not_an_absolute_http_link_is_none(not_a_link: str) -> None:
    assert canon_url(not_a_link) is None
