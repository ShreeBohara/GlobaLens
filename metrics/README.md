# metrics

The record every published number comes from. A number that is not in the ledger does not go
into the README or the docs.

## `ledger.jsonl`

One measured value per line, appended by a `bench/` or `evals/` script, never edited by hand.
The fields are the plan's (§13):

| Field | What |
|---|---|
| `metric` | What was measured, as one name |
| `value`, `unit` | The number and its unit |
| `ci` | Its interval, or null |
| `commit` | The commit the script ran on; `+dirty` when the working tree had changes |
| `dataset_version` | What it was measured on, specific enough to tell two inputs apart |
| `script` | The script that wrote the line |
| `ts` | When, in UTC |
| `label` | `measured`, `research` or `illustrative` |
| `source` | `production` (real data) or `synthetic` |
| `detail` | Everything else the script knows: counts, percentiles, budgets, the host |

The first lines are the data plane's (Phase 1 task 11, `bench/data_plane.py`): cold-start bytes,
bytes per update, title-shard bytes, the compression of the shards, and R2 writes per interval.
They are local-store measurements: the size of each object as stored in a folder, with no HTTP,
no edge and no cache, which their `detail.store` says. The same measurements on the bucket's
`r2.dev` address wait for R2.

## `claims.yml`

The claims the README and `/stats` make, each pointing at a ledger line. It arrives with the
first page that shows a number (Phase 1 task 17).
