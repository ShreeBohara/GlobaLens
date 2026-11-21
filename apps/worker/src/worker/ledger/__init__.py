"""The fenced ledger: depth kernel #1 (docs/design/p1.md §7).

    fence.py     leases on `ingest.interval`, and the commits that name the lease's token
    keys.py      object keys derived from content
    backoff.py   how long a failed file waits
    tier1.py     one lease walking one file through fetch, verify and load
    publish.py   the publisher's passes: loaded to published, fenced by the pass number

WALKTHROUGH.md, beside these files, explains them and changes with them.
"""
