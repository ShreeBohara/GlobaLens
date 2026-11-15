# bench

Benchmark scripts. Each one is a file here and a `bench:<name>` task in `mise.toml`, so
`mise run bench:<name>` is the only way a number in `metrics/ledger.jsonl` is produced.

`smoke.py` is a placeholder that proves the wiring. P1 task 9 moves `measure_gkg.py` and
`backfill_size.py` here from `docs/3.0/research/scripts/` and adds `parse_bench.py`.
