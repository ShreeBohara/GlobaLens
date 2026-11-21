"""The ingest worker.

    stamps.py     GDELT's 15-minute grid and its file names
    feed.py       GDELT's listing files, and HTTP
    poller.py     both `lastupdate` files every 60 seconds, into the ledger
    ledger/       the fenced ledger: leases, fenced commits, content keys, the tier-1 walk,
                  the publisher's passes
    lake.py       the lake's two Parquet files
    shards.py     the data plane's Arrow objects: point shards and title shards
    cells.py      H3 base cells, for the title shards
    manifest.py   now.json, the pass manifest, the hourly manifest, the title index
    dataplane.py  what a publishing pass writes, worked out from the ledger
    publisher.py  the publisher process: the lock, a pass every 30 seconds, the dead-man ping
    store.py      the object store: a folder for now
    db.py         the database connection

`python -m worker poll`, `python -m worker work` and `python -m worker publish` run the
poller, a tier-1 worker and the publisher.
"""
