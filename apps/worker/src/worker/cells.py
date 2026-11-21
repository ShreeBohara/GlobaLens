"""H3 res-0 base cells: the 122 cells that split the globe for the title shards.

The publisher stores each point's base cell in the point shard (`cell`), so the browser needs no
H3 library, and the page and the publisher can never put a point near a cell edge in two
different cells (docs/design/p1.md §6.3). The `h3` package does the geometry
(docs/adr/0012-h3.md).
"""

# h3 ships no type information, so its calls are unknown to pyright. This module is the only
# one that touches it; what goes in and what comes out are typed.
# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false

import h3

__all__ = ["CELLS", "base_cell"]

CELLS = 122
"""How many base cells H3 has. A cell is a number from 0 to 121."""


def base_cell(lat: float, lon: float) -> int:
    """The base cell, 0 to 121, that holds the point at `lat`, `lon` (degrees)."""
    number = h3.get_base_cell_number(h3.latlng_to_cell(lat, lon, 0))
    if not isinstance(number, int) or not 0 <= number < CELLS:
        raise ValueError(f"h3 gave base cell {number!r} for {lat}, {lon}")
    return number
