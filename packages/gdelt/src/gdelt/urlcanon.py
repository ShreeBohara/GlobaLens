"""URL canonicalization.

The canonical URL is the link a visitor opens, so every change made here leaves the same page
behind it:

- scheme and host in lower case (the path keeps its case);
- the default port removed (`:443` on https, `:80` on http);
- an empty path written as `/`;
- the fragment and any user name removed;
- tracking parameters removed (`TRACKING_PARAMETERS` and anything starting with `utm_`); the
  other parameters keep their order and their exact text.

It does not switch http to https, drop `www.`, `m.` or `/amp/`, change a trailing slash or
re-encode anything: each of those can break a link or point at another page. Matching copies
of one article across such variants is story grouping's job (Phase 2), not this function's.

Anything that is not an absolute http or https link, or that contains whitespace, control or
invisible characters, or is longer than `MAX_URL_CHARS`, gives `None`. That also keeps
`javascript:` and `data:` identifiers out of every `href`.
"""

import re
from urllib.parse import urlsplit

__all__ = ["MAX_URL_CHARS", "TRACKING_PARAMETERS", "canon_url"]

MAX_URL_CHARS = 2000

TRACKING_PARAMETERS = frozenset(
    {
        "fbclid", "gclid", "gclsrc", "dclid", "gbraid", "wbraid", "msclkid", "yclid", "twclid",
        "ttclid", "igshid", "mc_cid", "mc_eid", "_ga", "_gl", "_hsenc", "_hsmi", "__hsfp",
        "__hssc", "__hstc", "mkt_tok", "oly_anon_id", "oly_enc_id", "vero_id",
    }
)  # fmt: skip
"""Exact, lower-case names of parameters that only track the click. Kept short on purpose:
a name that is content on even one site (`ref`, `source`, `id`) is not here."""

# Whitespace, controls and invisible format characters. None belongs in a link.
_FORBIDDEN_CHARS = (
    "\x00-\x20\x7f-\xa0\u1680\u2000-\u200f"
    "\u2028-\u202f\u205f-\u206f\u3000\ufeff\ufff9-\ufffb\ud800-\udfff\U000e0000-\U000e007f"
)
_FORBIDDEN = re.compile(f"[{_FORBIDDEN_CHARS}]")

# Already canonical: lower-case scheme and host, no user name, port, query or fragment.
_CANONICAL = re.compile(rf"https?://[a-z0-9](?:[a-z0-9.\-]*[a-z0-9])?/[^?#{_FORBIDDEN_CHARS}]*")

_DEFAULT_PORT = {"http": 80, "https": 443}


def _is_tracking(segment: str) -> bool:
    name = segment.partition("=")[0].lower()
    return name.startswith("utm_") or name in TRACKING_PARAMETERS


def canon_url(url: str) -> str | None:
    """The canonical form of an absolute http(s) URL, or None if `url` is not one."""
    if len(url) > MAX_URL_CHARS:
        return None
    if _CANONICAL.fullmatch(url):
        return url
    if not url or _FORBIDDEN.search(url):
        return None
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        return None
    scheme = parts.scheme.lower()
    host = parts.hostname
    if scheme not in _DEFAULT_PORT or not host:
        return None
    if ":" in host:
        host = f"[{host}]"  # urlsplit hands back an IPv6 address without its brackets
    netloc = host if port is None or port == _DEFAULT_PORT[scheme] else f"{host}:{port}"
    query = parts.query
    if query:
        query = "&".join(seg for seg in query.split("&") if not _is_tracking(seg))
    path = parts.path or "/"
    return f"{scheme}://{netloc}{path}?{query}" if query else f"{scheme}://{netloc}{path}"
