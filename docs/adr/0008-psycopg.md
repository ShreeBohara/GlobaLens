# ADR-0008: psycopg 3 as the worker's PostgreSQL driver

Status: proposed · 2026-11-20 · Phase 1 (task 10) · Spine: none

## Context: the requirement or measurement that forces a decision (link the metric/ledger entry)

Phase 1 task 10 builds the fenced ledger (`docs/design/p1.md` §7): the poller and the tier-1
workers lease rows of `ingest.interval` and commit every step with the lease's token. Those are
SQL statements run from Python, and the repository has no PostgreSQL driver yet.

The tests need one as much as the code does. Task 8's SQL tests reach the database through
`psql` inside the container (ADR-0007), one script per call. The ledger's tests hold several
connections at once, keep a transaction open on one while another runs, and step workers one
statement at a time. ADR-0007 named this as the point at which a driver would arrive, with its
own ADR.

The owner approved adding `psycopg` with the task's plan on 20 November 2026. No metric is
involved, so there is no ledger entry.

## Prior: what you expect each option to measure, before measuring (bake-offs and triggers)

There was no bake-off, and no prior was written down before the work, so none is claimed.

## Options considered: each with cost, risk, ops burden, and the trigger that would change the answer

| Option | Why, or why not |
|---|---|
| psycopg 3 with the `binary` extra | **Chosen.** The current PostgreSQL driver for Python: typed (pyright strict reads it with no stubs), parameters bound by the server, a plain synchronous API. The extra installs `psycopg-binary`, a wheel that carries its own libpq, so nothing has to be installed on the machine or in the image |
| psycopg 3 with the `c` extra | The same driver compiled against the system's libpq. It needs a compiler and the libpq headers wherever it is installed. That is a choice for the image (task 7), not for a developer's Mac |
| psycopg 3 alone | Pure Python over a libpq found on the machine. The owner's Mac has one of unknown version; the result would differ from machine to machine |
| asyncpg | Asyncio only, with its own implementation of the protocol. The kernel is synchronous on purpose: a walk is a generator that the property test steps by hand |
| psycopg2 | In maintenance; no type information; binds parameters on the client |
| pg8000 | Pure Python and small, but slower and less used |

**Testcontainers is not adopted.** The design note names it for these tests (§7.7). The owner
approved the departure with the plan: the tests reuse task 8's harness, which starts the pinned
PostgreSQL 18 image with the `docker` command, and connect to it with psycopg. One dependency
fewer, and the database is just as real.

Trigger to revisit the extra: task 7 builds the worker's image. If that image has libpq and a
compiler, `psycopg[c]` there removes the bundled libpq and OpenSSL. Trigger to revisit the
driver: a need for asyncio in the worker.

## Decision: exactly one choice

Add `psycopg[binary]==3.3.8` as a dependency of `globalens-worker` (`apps/worker/pyproject.toml`),
pinned exactly. It brings two packages, `psycopg` and `psycopg-binary`, both 3.3.8 and both
released on 2026-11-04, which is inside the cooldown ADR-0001 sets (`exclude-newer` is
2026-11-08). On Windows it would also bring `tzdata`; `uv.lock` records it and neither node
installs it.

How it is used:

- `worker.db.connect` opens every connection in autocommit mode and in UTC. The ledger refuses
  a connection that is not in autocommit mode, because each of its calls is meant to be its own
  transaction.
- One connection per process and no pool.
- Every statement is a literal string in `apps/worker/src/worker/ledger/fence.py`; values go in
  as parameters, never into the text.

**Licence.** psycopg and psycopg-binary are LGPL-3.0-only. The repository is Apache-2.0. The
worker imports psycopg unmodified, as a separate package, and no code is copied from it, so
`CLAUDE.md`'s rule about copied code is not touched. It is still the first dependency here
that is not under a permissive licence, so it is stated plainly for the owner to accept. The
wheel also carries libpq (PostgreSQL licence), OpenSSL (Apache-2.0), and Kerberos and LDAP
client libraries.

## Evidence: bench/eval/bake-off links; pre-registration; prior vs measured

Run on the owner's Mac (Apple M3 Pro, macOS, Docker Desktop, linux/arm64 containers) on
2026-11-20 UTC:

- `mise run check` passes with psycopg imported under pyright's strict mode.
- `mise run test:ledger` passes: the ledger's tests run as the role `worker` over TCP against
  the pinned PostgreSQL 18.6 image, with up to eight connections leasing at once.
- The poller and two workers ran against live GDELT and a local PostgreSQL 18.6 with this
  driver (the manual run of task 10; its figures are in the pull request, not here).
- `uv.lock` lists `psycopg-binary` wheels for CPython 3.13 on macOS arm64 and on Linux x86-64
  and aarch64 (glibc and musl). The bundled libpq reports version 18.0.6
  (`psycopg.pq.version()`).

Not verified: the driver on Linux or on amd64 (the Mac is arm64 and CI does not exist yet);
password or TLS connections (the test container uses trust authentication on 127.0.0.1).

## Consequences: what gets easier/harder; rollback plan; what we will measure next

**Easier.** The kernel's SQL runs as written, with typed parameters, and the tests can hold a
transaction open on one connection while another works.

**Harder.** The wheel's libpq and OpenSSL are updated only by a new psycopg release, so a
security fix in either arrives as a version bump. Renovate (task 5) has to watch the pin.
An image that ships psycopg has to carry its licence text.

**Rollback.** The product code imports psycopg in two places: `worker/db.py`, which opens the
connection, and `worker/ledger/fence.py`, for the connection's type. The statements are plain
SQL with named parameters, so another driver that binds named parameters could run them. The
tests use psycopg directly and would change with it.

**Next.** Task 5 runs `mise run test:ledger` in CI on both architectures. Task 7 decides
between the `binary` and the `c` extra for the image.
