"""Plain-JSON views of parse results, for golden files, logs and debugging."""

from typing import Any

from gdelt.parse import LeanRow, ParseResult

__all__ = ["result_to_json", "row_to_json"]


def row_to_json(row: LeanRow) -> dict[str, Any]:
    """A `LeanRow` as JSON-ready values: timestamps in ISO 8601, the title hash in hex."""
    primary = row.primary
    return {
        "record_id": row.record_id,
        "stream": row.stream.value,
        "seq": row.seq,
        "stamp": row.stamp.isoformat(),
        "outlet": row.outlet,
        "url": row.url,
        "title": row.title,
        "title_hash": row.title_hash.hex() if row.title_hash is not None else None,
        "published_at": row.published_at.isoformat() if row.published_at is not None else None,
        "srclc": row.srclc,
        "lang": row.lang.tag if row.lang is not None else None,
        "lang_index": row.lang.index if row.lang is not None else None,
        "translation_info": row.translation_info,
        "tone": list(row.tone) if row.tone is not None else None,
        "themes": list(row.themes),
        "locations": [loc._asdict() for loc in row.locations],
        "primary": primary._asdict() | {"is_point": primary.is_point} if primary else None,
    }


def result_to_json(result: ParseResult) -> dict[str, Any]:
    """A whole parse result. Quarantined lines are given by line number and reason."""
    stats = result.stats
    return {
        "rows": [row_to_json(row) for row in result.rows],
        "quarantined": [
            {"line_no": q.line_no, "reason": q.reason.value, "bytes": len(q.raw)}
            for q in result.quarantined
        ],
        "stats": {
            "lines": stats.lines,
            "rows": stats.rows,
            "blank_lines": stats.blank_lines,
            "quarantined": dict(sorted(stats.quarantined.items())),
            "issues": dict(sorted(stats.issues.items())),
            "unknown_srclc": dict(sorted(stats.unknown_srclc.items())),
            "malformed_share": round(stats.malformed_share, 6),
        },
    }
