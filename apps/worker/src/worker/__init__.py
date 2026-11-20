"""The ingest worker.

    stamps.py     GDELT's 15-minute grid and its file names
    feed.py       GDELT's listing files, and HTTP
    poller.py     both `lastupdate` files every 60 seconds, into the ledger
    ledger/       the fenced ledger: leases, fenced commits, content keys, the tier-1 walk
    lake.py       the lake's two Parquet files
    store.py      the object store: a folder for now
    db.py         the database connection

`python -m worker poll` and `python -m worker work` run the poller and a tier-1 worker. The
publisher arrives with Phase 1 task 11.
"""
