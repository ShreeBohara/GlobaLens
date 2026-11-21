"""What a publishing pass writes: built from the ledger, complete for a cold client, and the
same keys for the same rows.

No database here: the ledger rows are written out by hand. Every title, URL and outlet name is
invented (`.example` domains).
"""

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import h3  # pyright: ignore[reportMissingTypeStubs]
from gdelt import Stream, parse_gkg
from worker import dataplane, lake, manifest, shards
from worker.dataplane import Interval, Plan
from worker.ledger.keys import lake_keys
from worker.stamps import format_stamp
from worker.store import MemoryStore

# 14:00 to 14:59 is the open hour until the cut at 15:15.
HOUR = datetime(2026, 11, 14, 14, 0, tzinfo=UTC)
Q = timedelta(minutes=15)

PLACES = [
    "4#Kyiv, Kyiv, Ukraine#UP#UP12#80247#50.4333#30.5167#-1044367#40",
    "4#Lyon, Rhone-Alpes, France#FR#FRB9#69#45.75#4.85#-1445171#58",
    "3#Austin, Texas, United States#US#USTX#TX453#30.2672#-97.7431#1384879#977",
    "1#Ukraine#UP#UP##49#32#UP#10",
    "5#Kyiv, Ukraine#UP#UP12##50.4333#30.5167#-1044367#40",
    "",
]


def gkg(stream: Stream, stamp: datetime, rows: int) -> bytes:
    text = format_stamp(stamp)
    lines: list[bytes] = []
    for number in range(1, rows + 1):
        columns = [""] * 27
        columns[0] = f"{text}-{'T' if stream is Stream.TRANSLATED else ''}{number}"
        columns[1] = text
        columns[2] = "1"
        columns[3] = f"outlet-{number % 5}.example"
        columns[4] = f"https://outlet-{number % 5}.example/{stream.value}/{text}/{number}"
        columns[10] = PLACES[number % len(PLACES)]
        columns[15] = "-2.5,1.5,4,5.5,20,0.5,310"
        columns[25] = "srclc:fra;eng:GT-FRA 1.0" if stream is Stream.TRANSLATED else ""
        columns[26] = f"<PAGE_TITLE>Synthetic headline {number} of {text}</PAGE_TITLE>"
        lines.append("\t".join(columns).encode())
    return b"\n".join(lines) + b"\n"


class Ledger:
    """A store with lake files in it, and the ledger rows that name them."""

    def __init__(self) -> None:
        self.store = MemoryStore()
        self.rows: dict[tuple[Stream, datetime], Interval] = {}

    def load(self, stream: Stream, stamp: datetime, rows: int = 12) -> Interval:
        parsed = parse_gkg(gkg(stream, stamp, rows))
        facts, display = lake.build(parsed.rows, parsed.stats)
        facts_key, display_key = lake_keys(stream, stamp, facts, display)
        self.store.put(facts_key, facts)
        self.store.put(display_key, display)
        interval = Interval(stream, stamp, facts_key, listed_at=stamp - timedelta(minutes=9))
        self.rows[(stream, stamp)] = interval
        return interval

    def publish(self, intervals: list[Interval], seq: int, at: datetime) -> None:
        for i in intervals:
            self.rows[(i.stream, i.stamp)] = Interval(
                i.stream, i.stamp, i.parquet_key, i.listed_at, seq=seq, published_at=at
            )

    def published(self) -> list[Interval]:
        return [i for i in self.rows.values() if i.seq is not None]


def write(store: MemoryStore, plan: Plan) -> None:
    for put in plan.puts:
        store.put(put.key, put.data)
    store.put(dataplane.NOW_KEY, plan.now)


def run(
    ledger: Ledger, plane: dataplane.DataPlane, ready: list[Interval], seq: int, at: datetime
) -> Plan:
    """One pass: plan, write everything, commit."""
    plan = plane.plan(seq=seq, now=at, ready=ready, published=ledger.published())
    write(ledger.store, plan)
    ledger.publish(ready, seq, at)
    plane.committed(plan)
    return plan


def both(ledger: Ledger, stamp: datetime) -> list[Interval]:
    return [ledger.load(Stream.ENGLISH, stamp), ledger.load(Stream.TRANSLATED, stamp)]


def plane_for(ledger: Ledger) -> dataplane.DataPlane:
    return dataplane.DataPlane(dataplane.lake_reader(ledger.store.get))


# --- The cut and the window ----------------------------------------------------------------


def test_the_cut_is_a_quarter_past_and_the_window_is_24_closed_hours() -> None:
    assert dataplane.cut_of(HOUR + timedelta(minutes=14)) == HOUR - timedelta(minutes=45)
    assert dataplane.cut_of(HOUR + timedelta(minutes=15)) == HOUR + timedelta(minutes=15)
    assert dataplane.cut_of(HOUR + timedelta(minutes=59)) == HOUR + timedelta(minutes=15)
    assert dataplane.window_start(HOUR + timedelta(minutes=20)) == HOUR - timedelta(hours=24)


# --- What a cold client sees ---------------------------------------------------------------


def test_every_published_interval_in_the_window_is_reachable_through_two_manifests() -> None:
    ledger = Ledger()
    plane = plane_for(ledger)
    stamps = [HOUR - timedelta(hours=2) + n * Q for n in range(12)]  # 12:00 to 14:45
    for seq, stamp in enumerate(stamps, start=1):
        run(ledger, plane, both(ledger, stamp), seq, stamp + timedelta(minutes=8))
        cold = dataplane.cold_start(ledger.store.get)
        assert cold.intervals == {(i.stream, i.stamp) for i in ledger.published()}
        assert cold.now.seq == seq
        # Each cell's titles are reachable too.
        for unit in cold.manifest.open:
            for ref in unit.titles.cells.values():
                assert ledger.store.get("cdn/" + ref.key) is not None
    # At 14:53 the cut is 14:15: 12:00 and 13:00 are compacted, 14:00 is open.
    cold = dataplane.cold_start(ledger.store.get)
    assert cold.hourly is not None
    assert [h.hour for h in cold.hourly.hours] == [
        HOUR - timedelta(hours=2),
        HOUR - timedelta(hours=1),
    ]
    assert {u.stamp for u in cold.manifest.open} == {HOUR + n * Q for n in range(4)}


def test_a_closed_hour_is_compacted_at_the_cut_and_leaves_the_open_list() -> None:
    ledger = Ledger()
    plane = plane_for(ledger)
    for n in range(4):
        run(ledger, plane, both(ledger, HOUR + n * Q), n + 1, HOUR + n * Q + timedelta(minutes=8))
    before = dataplane.cold_start(ledger.store.get)
    assert before.hourly is None and len(before.manifest.open) == 4

    # 15:15: the cut closes 14:00 to 14:59.
    plan = run(ledger, plane, [], 5, HOUR + timedelta(hours=1, minutes=15))
    after = dataplane.cold_start(ledger.store.get)
    assert after.manifest.open == ()
    assert after.hourly is not None
    (hour,) = after.hourly.hours
    assert hour.hour == HOUR
    assert hour.stamps == {s: tuple(HOUR + n * Q for n in range(4)) for s in Stream}
    assert after.intervals == before.intervals
    assert {put.kind for put in plan.puts} >= {
        "hour-points",
        "hour-titles",
        "hour-index",
        "hour-manifest",
    }


def test_a_compaction_holds_exactly_the_rows_of_its_hours_units() -> None:
    ledger = Ledger()
    plane = plane_for(ledger)
    units: list[manifest.Unit] = []
    for n in range(4):
        plan = run(
            ledger, plane, both(ledger, HOUR + n * Q), n + 1, HOUR + n * Q + timedelta(minutes=8)
        )
        units.append(plan.open[-1])
    run(ledger, plane, [], 5, HOUR + timedelta(hours=1, minutes=15))
    cold = dataplane.cold_start(ledger.store.get)
    assert cold.hourly is not None
    (hour,) = cold.hourly.hours

    def points(ref: manifest.Points) -> list[shards.PointRow]:
        data = ledger.store.get("cdn/" + ref.ref.key)
        assert data is not None
        return shards.read_points(data, ref.points)

    def area_total(ref: manifest.Points) -> int:
        data = ledger.store.get("cdn/" + ref.ref.key)
        assert data is not None
        return sum(row.n for row in shards.read_areas(data, ref.areas))

    rows = [row for unit in units for row in points(unit.points)]
    expected = sorted(rows, key=lambda row: (row.iv, row.key))
    assert points(hour.points) == expected
    assert area_total(hour.points) == sum(area_total(unit.points) for unit in units)

    index_data = ledger.store.get("cdn/" + hour.titles.key)
    assert index_data is not None
    _, index = manifest.read_title_index(index_data)
    compacted: set[tuple[int, int]] = set()
    for ref in {ref.key: ref for ref in index.cells.values()}.values():
        data = ledger.store.get("cdn/" + ref.key)
        assert data is not None
        compacted |= {(row.iv, row.key) for row in shards.read_titles(data)}
    unit_titles: set[tuple[int, int]] = set()
    for unit in units:
        for ref in {ref.key: ref for ref in unit.titles.cells.values()}.values():
            data = ledger.store.get("cdn/" + ref.key)
            assert data is not None
            unit_titles |= {(row.iv, row.key) for row in shards.read_titles(data)}
    assert compacted == unit_titles


def test_a_unit_published_after_the_cut_stays_open_until_the_next_cut() -> None:
    ledger = Ledger()
    plane = plane_for(ledger)
    for n in range(3):
        run(ledger, plane, both(ledger, HOUR + n * Q), n + 1, HOUR + n * Q + timedelta(minutes=8))
    run(ledger, plane, [], 4, HOUR + timedelta(hours=1, minutes=15))
    # The 14:45 stamp arrives late, at 15:40: its hour is closed, its unit is open.
    late = both(ledger, HOUR + 3 * Q)
    run(ledger, plane, late, 5, HOUR + timedelta(hours=1, minutes=40))
    cold = dataplane.cold_start(ledger.store.get)
    assert cold.hourly is not None
    assert cold.hourly.hours[0].stamps[Stream.ENGLISH] == tuple(HOUR + n * Q for n in range(3))
    assert [u.stamp for u in cold.manifest.open] == [HOUR + 3 * Q]
    # 16:15: the next cut folds it into its hour's compaction.
    run(ledger, plane, [], 6, HOUR + timedelta(hours=2, minutes=15))
    cold = dataplane.cold_start(ledger.store.get)
    assert cold.manifest.open == ()
    assert cold.hourly is not None
    assert cold.hourly.hours[0].stamps[Stream.ENGLISH] == tuple(HOUR + n * Q for n in range(4))


def test_a_late_stream_is_a_unit_of_its_own() -> None:
    ledger = Ledger()
    plane = plane_for(ledger)
    english = ledger.load(Stream.ENGLISH, HOUR)
    run(ledger, plane, [english], 1, HOUR + timedelta(minutes=20))
    translated = ledger.load(Stream.TRANSLATED, HOUR)
    run(ledger, plane, [translated], 2, HOUR + timedelta(minutes=40))
    cold = dataplane.cold_start(ledger.store.get)
    assert [(u.stamp, u.streams) for u in cold.manifest.open] == [
        (HOUR, (Stream.ENGLISH,)),
        (HOUR, (Stream.TRANSLATED,)),
    ]


def test_intervals_older_than_the_window_are_not_shown() -> None:
    ledger = Ledger()
    plane = plane_for(ledger)
    old = both(ledger, HOUR - timedelta(hours=30))
    plan = run(ledger, plane, old, 1, HOUR + timedelta(minutes=20))
    assert plan.open == () and plan.hours == ()
    assert {put.kind for put in plan.puts} == {"manifest"}
    assert dataplane.cold_start(ledger.store.get).intervals == frozenset()


def test_now_json_names_the_newest_stamp_of_each_stream_and_its_listing_time() -> None:
    ledger = Ledger()
    plane = plane_for(ledger)
    run(ledger, plane, both(ledger, HOUR), 1, HOUR + timedelta(minutes=8))
    run(ledger, plane, [ledger.load(Stream.ENGLISH, HOUR + Q)], 2, HOUR + timedelta(minutes=40))
    now = manifest.read_now(ledger.store.get(dataplane.NOW_KEY) or b"")
    assert now.seq == 2
    assert now.written_at == HOUR + timedelta(minutes=40)
    english, translated = now.streams[Stream.ENGLISH], now.streams[Stream.TRANSLATED]
    assert english is not None and english.stamp == HOUR + Q
    assert english.listed_at == HOUR + Q - timedelta(minutes=9)
    assert translated is not None and translated.stamp == HOUR


# --- Order, keys and memory ----------------------------------------------------------------


def names(data: bytes) -> set[str]:
    """Every object key a JSON file names."""
    found: set[str] = set()

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            items: dict[str, Any] = value  # pyright: ignore[reportUnknownVariableType]
            for key, item in items.items():
                if key in ("key", "hour", "manifest") and isinstance(item, str) and "/" in item:
                    found.add("cdn/" + item)
                else:
                    walk(item)
        elif isinstance(value, list):
            entries: list[Any] = value  # pyright: ignore[reportUnknownVariableType]
            for item in entries:
                walk(item)

    walk(json.loads(data))
    return found


def test_every_object_names_only_objects_written_before_it() -> None:
    ledger = Ledger()
    plane = plane_for(ledger)
    for n in range(8):  # two cuts' worth: 14:00 to 15:45
        stamp = HOUR + n * Q
        at = stamp + timedelta(minutes=8)
        ready = both(ledger, stamp)
        plan = plane.plan(seq=n + 1, now=at, ready=ready, published=ledger.published())
        before = set(ledger.store.objects)
        for put in plan.puts:
            assert dataplane.is_content_key(put.key, put.data)
            if put.key.endswith(".json"):
                assert names(put.data) <= before
            ledger.store.put(put.key, put.data)
            before.add(put.key)
        assert names(plan.now) <= before
        assert plan.puts[-1].key == plan.manifest_key
        ledger.store.put(dataplane.NOW_KEY, plan.now)
        ledger.publish(ready, n + 1, at)
        plane.committed(plan)


def test_a_fresh_planner_gives_the_same_keys_and_bytes() -> None:
    ledger = Ledger()
    plane = plane_for(ledger)
    for n in range(4):
        run(ledger, plane, both(ledger, HOUR + n * Q), n + 1, HOUR + n * Q + timedelta(minutes=8))
    at = HOUR + timedelta(hours=1, minutes=20)
    ready = [ledger.load(Stream.ENGLISH, HOUR + 4 * Q)]
    warm = plane.plan(seq=9, now=at, ready=ready, published=ledger.published())
    cold = plane_for(ledger).plan(seq=9, now=at, ready=ready, published=ledger.published())
    assert cold.now == warm.now
    assert cold.named == warm.named
    assert {p.key: p.data for p in warm.puts}.items() <= {p.key: p.data for p in cold.puts}.items()


def test_after_a_commit_nothing_already_written_is_put_again() -> None:
    ledger = Ledger()
    plane = plane_for(ledger)
    run(ledger, plane, both(ledger, HOUR), 1, HOUR + timedelta(minutes=8))
    plan = plane.plan(
        seq=2, now=HOUR + timedelta(minutes=9), ready=[], published=ledger.published()
    )
    assert [put.kind for put in plan.puts] == ["manifest"]


def test_a_pass_is_due_for_ready_intervals_or_a_new_cut() -> None:
    ledger = Ledger()
    plane = plane_for(ledger)
    ready = both(ledger, HOUR)
    assert plane.due(HOUR + timedelta(minutes=8), ready, [])
    assert not plane.due(HOUR + timedelta(minutes=8), [], [])  # nothing in the window
    run(ledger, plane, ready, 1, HOUR + timedelta(minutes=8))
    assert not plane.due(HOUR + timedelta(minutes=9), [], ledger.published())
    assert plane.due(HOUR + timedelta(hours=1, minutes=15), [], ledger.published())
    # A planner that has not run yet makes one pass, to rewrite now.json.
    assert plane_for(ledger).due(HOUR + timedelta(minutes=9), [], ledger.published())


def test_an_hours_compaction_writes_at_most_59_cell_title_objects() -> None:
    """With the compaction's own five other objects, the pass manifest and now.json, the cut's
    pass then stays within the plan's 65 writes an hour."""
    centres: list[tuple[float, float]] = [
        h3.cell_to_latlng(cell)  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
        for cell in sorted(h3.get_res0_cells())  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType, reportUnknownArgumentType]
    ]
    ledger = Ledger()
    plane = plane_for(ledger)
    lines: list[bytes] = []
    text = format_stamp(HOUR)
    for number, (lat, lon) in enumerate(centres[:70], start=1):
        columns = [""] * 27
        columns[0] = f"{text}-{number}"
        columns[1] = text
        columns[2] = "1"
        columns[3] = "outlet.example"
        columns[4] = f"https://outlet.example/{number}"
        columns[10] = f"4#Somewhere#XX#XX01##{lat:.4f}#{lon:.4f}#-1#10"
        columns[15] = "-2.5,1.5,4,5.5,20,0.5,310"
        columns[26] = f"<PAGE_TITLE>Synthetic headline {number}</PAGE_TITLE>"
        lines.append("\t".join(columns).encode())
    parsed = parse_gkg(b"\n".join(lines) + b"\n")
    facts, display = lake.build(parsed.rows, parsed.stats)
    facts_key, display_key = lake_keys(Stream.ENGLISH, HOUR, facts, display)
    ledger.store.put(facts_key, facts)
    ledger.store.put(display_key, display)
    interval = Interval(Stream.ENGLISH, HOUR, facts_key, listed_at=HOUR)
    unit = run(ledger, plane, [interval], 1, HOUR + timedelta(minutes=8))
    assert sum(1 for p in unit.puts if p.kind == "titles") == shards.MAX_TITLE_SHARDS
    cut = run(ledger, plane, [], 2, HOUR + timedelta(hours=1, minutes=15))
    kinds = [p.kind for p in cut.puts]
    assert kinds.count("hour-titles") == dataplane.HOURLY_TITLE_SHARDS == 59
    assert len(cut.puts) + 1 <= 65  # and now.json
