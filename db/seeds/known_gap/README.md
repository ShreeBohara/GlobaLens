# The June 2025 gap: where the seed comes from

`ingest.known_gap` is seeded by `0001_ingest.sql` with one row per stream for the files GDELT
never published in June and July 2025. The rows are not typed by hand. They are read from the
output of the master-list script, saved here:

| File | What it is |
|---|---|
| `english.txt` | The script's output for `masterfilelist.txt`, unedited |
| `translated.txt` | The script's output for `masterfilelist-translation.txt`, unedited |

`db/seedgen.py` reads the block "Top gaps since 2024 for gkg" in each file, takes the longest
run, refuses it unless it starts in June 2025, and writes the rows into the migration.
`last_stamp` is the last missing stamp, inclusive: the start plus (count − 1) × 15 minutes.

## The run (measured)

Run on 16 November 2026 UTC from the repository root, with the script as it stood at commit
`157aae0` (SHA-256 `c035808a…e5528bb1`), unmoved and unedited.

```bash
curl -sS --fail -o "$LISTS/masterfilelist.txt" https://data.gdeltproject.org/gdeltv2/masterfilelist.txt
curl -sS --fail -o "$LISTS/masterfilelist-translation.txt" https://data.gdeltproject.org/gdeltv2/masterfilelist-translation.txt
uv run --no-sync python -I docs/3.0/research/scripts/analyze_masterlist.py "$LISTS/masterfilelist.txt" english > db/seeds/known_gap/english.txt
uv run --no-sync python -I docs/3.0/research/scripts/analyze_masterlist.py "$LISTS/masterfilelist-translation.txt" translated > db/seeds/known_gap/translated.txt
```

`$LISTS` stands for a folder outside the repository: the two lists are about 130 MB each and
are not committed. In the run itself the output went to that folder first and was copied here
unchanged. Python was 3.13.5, the one uv manages, started through `mise exec --`.

| List | Bytes | Lines | `Last-Modified` | SHA-256 |
|---|---|---|---|---|
| `masterfilelist.txt` | 129,534,973 | 1,213,164 | 2026-11-16 00:49:22 GMT | `d3f8dd6b884e99d9d9179c716a865016e434a3a88fe183e4cf011e7be085d086` |
| `masterfilelist-translation.txt` | 142,068,272 | 1,197,333 | 2026-11-16 00:49:07 GMT | `8f5ea8d33935b7c0b3f08890d190e9774a7f8e980fc217e9a3d09f1c7e782580` |

## What the run found

| Stream | First missing stamp (UTC) | Last missing stamp (UTC) | Intervals |
|---|---|---|---|
| english | 2025-06-14 18:00 | 2025-07-02 02:00 | 1,665 |
| translated | 2025-06-14 17:45 | 2025-07-02 02:00 | 1,666 |

Both rows agree with the per-stream bounds in `docs/3.0/research/data-gdelt.md` (fact-check
row 6). The master plan's one figure, "2025-06-14 18:00 to about 07-02, 1,665 intervals", is the
English stream's.

Checked a second way, straight from the lists: the last gkg file before the gap is `17:45`
(english) and `17:30` (translated) on 14 June, the first one after it is `02:15` on 2 July in
both, and neither list has an entry of any type in between.

## Not seeded

The script's output also shows shorter runs of missing files: 9 intervals from 2025-06-12 18:15
in the English stream (10 from 18:00 in the translated one), and single missing stamps on ten
other days since 2024, each one interval longer in the translated stream. Task 8 seeds the long
gap only, as the design note asks (§5). Whether the short ones belong in `ingest.known_gap`
matters when the backfill starts (Phase 6), not before.

## Running it again

The lists grow every 15 minutes, so a new run changes the numbers in the output that do not
matter here and the "list read up to" time in each row's `reason`. To take a new run:
replace the two files, then `uv run --no-sync python db/seedgen.py write`. Once `0001` has
been applied to production its text is frozen, and a change goes in a new migration.

In Phase 1 task 9 the script moves from `docs/3.0/research/scripts/` to `bench/`; the command
above then needs the new path. The saved output does not depend on where the script lives.
