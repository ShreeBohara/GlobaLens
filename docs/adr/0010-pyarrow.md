# ADR-0010: pyarrow, pinned exactly, to write the lake's Parquet

Status: proposed · 2026-11-20 · Phase 1 (task 10) · Spine: none

## Context: the requirement or measurement that forces a decision (link the metric/ledger entry)

The load step of the tier-1 worker writes two Parquet files per GKG file to the lake: facts,
and display (`docs/design/p1.md` §6). The plan names the stack for the lake: Parquet on R2,
DuckDB on the free node, and pyarrow (§6, "Lake + cubes").

One requirement is specific to the ledger. Every object a worker writes goes to a key derived
from its content (§7.4), so that two workers doing the same step write the same bytes to the
same key. For the lake that only holds if **the same rows give the same bytes on every run**.

The owner approved adding `pyarrow` with the task's plan on 20 November 2026. No metric is
involved, so there is no ledger entry.

## Prior: what you expect each option to measure, before measuring (bake-offs and triggers)

There was no bake-off: the plan had named the library. No prior was written down before the
work, so none is claimed.

## Options considered: each with cost, risk, ops burden, and the trigger that would change the answer

| Option | Why, or why not |
|---|---|
| pyarrow | **Chosen.** The reference Parquet writer; every option that decides the bytes (format version, page version, codec and level, dictionary, statistics, row groups) can be fixed in the call. No other package comes with it |
| DuckDB's Python package | Writes Parquet with `COPY`. The plan runs DuckDB on the free node, to read the lake. Using it to write, from Python rows, would bring a second large package now and leaves fewer of the bytes under our control |
| fastparquet | Needs pandas and numpy, and is less widely used |
| polars | Its own writer and a large package; nothing else here uses it |

Trigger to revisit: the publisher (task 11) reads these files and writes Arrow shards, with
pyarrow or with another reader. If it brings another Arrow implementation, the two are weighed
then.

## Decision: exactly one choice

Add `pyarrow==26.0.1` as a dependency of `globalens-worker`, pinned exactly. It was released on
2026-11-03, inside ADR-0001's cooldown, and brings no other package.

The pin is part of the design, not only supply-chain hygiene. The bytes of a Parquet file
depend on the writer's version, so:

- `apps/worker/src/worker/lake.py` is the only module that imports pyarrow. It fixes every
  writer option: format 2.6, data pages 1.0, zstd at level 9, dictionary encoding and
  statistics on, the Arrow schema stored, one row group. Rows are written in file order.
- A unit test builds the same input twice, and again in two other processes with different hash
  seeds, and compares the bytes.
- A new pyarrow version is a dependency pull request of its own. If it writes different bytes
  for the same rows, nothing breaks: a file loaded after the change gets a new key, and every
  key the ledger already names still holds what it held.

## Evidence: bench/eval/bake-off links; pre-registration; prior vs measured

Run on the owner's Mac (Apple M3 Pro) on 2026-11-20 UTC:

- `mise run check` passes, with the test that the same rows give the same bytes in one process
  and across processes.
- In the 1,000-history property test (`mise run test:ledger`) the object store fails a history
  if any key is ever written twice with different bytes. None was.
- In the manual run against live GDELT every loaded file's two Parquet objects were written
  under one name with one content hash (figures in the pull request).
- `uv.lock` lists wheels for CPython 3.13 on macOS arm64 and on Linux x86-64 and aarch64.

**Not verified: that linux/amd64 and linux/arm64 write the same bytes.** Everything above ran
on arm64. If the two differ, the same file loaded once on each node would get two keys, of
which the ledger names one. That is harmless to correctness and wasteful in a bucket that will
be locked, so it has to be checked before both nodes load (Phase 2), and can be checked as soon
as CI runs on both architectures (task 5).

Also not verified: reading these files with DuckDB.

## Consequences: what gets easier/harder; rollback plan; what we will measure next

**Easier.** The lake is ordinary Parquet from the first loaded file, readable by DuckDB and by
anything else.

**Harder.** pyarrow is by far the largest dependency of the worker, and the image (task 7)
carries it. It ships no type information, so `lake.py` turns off four of pyright's
unknown-type checks for itself; what goes into the module and what comes out are typed.

**The schema is version 1 and proposed.** The design note gives the two files' column families
and not their columns. `lake.py` writes, in facts: record ID and number, stamp, publication
time, outlet, language, title hash, the primary location, tone, themes and every location
mentioned; in display: record number, title, URL. The key carries `v1`, and the facts file's
metadata carries the parser's counts, including the quarantined lines. Task 11 is the first
reader and may ask for changes; the bucket lock does not start before the Phase 1 close (Q17).

**Rollback.** Replace `lake.py`. Nothing else knows the files are written by pyarrow.

**Next.** The cross-architecture check above. Task 11 reads the files and measures their size.
