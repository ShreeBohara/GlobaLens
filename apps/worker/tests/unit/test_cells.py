"""H3 base cells for the title shards."""

# h3 ships no type information, so its calls are unknown to pyright.
# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false

import h3
from hypothesis import given
from hypothesis import strategies as st
from worker.cells import CELLS, base_cell


def test_every_base_cell_holds_its_own_centre() -> None:
    cells = sorted(h3.get_res0_cells())
    assert len(cells) == CELLS
    numbers = set()
    for cell in cells:
        lat, lon = h3.cell_to_latlng(cell)
        number = base_cell(lat, lon)
        assert number == h3.get_base_cell_number(cell)
        numbers.add(number)
    assert numbers == set(range(CELLS))


def test_the_poles_and_the_antimeridian_have_cells() -> None:
    for lat, lon in [(90.0, 0.0), (-90.0, 0.0), (0.0, 180.0), (0.0, -180.0), (89.9, 179.9)]:
        assert 0 <= base_cell(lat, lon) < CELLS


@given(
    st.floats(min_value=-90, max_value=90, allow_nan=False),
    st.floats(min_value=-180, max_value=180, allow_nan=False),
)
def test_any_point_has_one_cell_and_always_the_same(lat: float, lon: float) -> None:
    number = base_cell(lat, lon)
    assert 0 <= number < CELLS
    assert base_cell(lat, lon) == number
