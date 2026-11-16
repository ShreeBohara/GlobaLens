# bench

Benchmark and measurement scripts. A number in `metrics/ledger.jsonl` is produced by a
`mise run bench:<name>` task and by nothing else.

| Script | Task | What it measures |
|---|---|---|
| `smoke.py` | `bench:smoke` | Nothing: a placeholder that proves the wiring |
| `parse_bench.py` | `bench:parse` | Rows per second of `packages/gdelt` on one core, from unzipped bytes to lean rows |

`mise run bench:parse` on its own runs on synthetic rows, which shows that the benchmark
works and is not a result. For a result, give it real GKG files and, to record it, the ledger:

    mise run bench:parse -- --ledger metrics/ledger.jsonl /path/to/gkg/files

Real GKG files are public and free, and they are never committed: keep them outside the
repository.

## Research scripts

`measure_gkg.py`, `backfill_size.py` and `analyze_masterlist.py` produced the numbers in
`docs/3.0/research/data-gdelt.md`. P1 task 9 moved them here from `docs/3.0/research/scripts/`
and tidied them for the linter and the type checker; what they compute and print is unchanged.
They have no `bench:` task. Each is run by hand on downloaded files, with the usage line at
the top of the file:

    uv run --no-sync python -I bench/measure_gkg.py /path/to/*.gkg.csv.zip
    uv run --no-sync python -I bench/analyze_masterlist.py /path/to/masterfilelist.txt english
    uv run --no-sync python -I bench/backfill_size.py masterfilelist.txt masterfilelist-translation.txt sample.gkg.csv.zip

`measure_gkg.py` keeps its own naive parser on purpose, so that its numbers stay comparable
with the research report. `parse_bench.py` measures the real one.
