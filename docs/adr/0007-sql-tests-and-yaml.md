# ADR-0007: SQL tests on a pinned PostgreSQL 18 image, and PyYAML for `prov/sources.yml`

Status: proposed · 2026-11-15 · Phase 1 (task 8) · Spine: none

## Context: the requirement or measurement that forces a decision (link the metric/ledger entry)

Phase 1 task 8 writes the first migration, `db/migrations/0001_ingest.sql`. Two things about it
cannot be done with what the skeleton (ADR-0001) installed:

1. **The migration has to be proved on a real PostgreSQL 18.** The design note's test for the
   task is that it "applies to a clean PG18 and the SQL tests pass" (`docs/design/p1.md` §9,
   task 8). No PostgreSQL is pinned anywhere in the repository yet: the production image arrives
   with task 7.
2. **The `prov.source` seed has to be generated from `prov/sources.yml`.** The plan makes that
   file the source of truth for upstream datasets (Appendix D), and the design note has the
   migration's seed generated from it, with a test that fails when the two differ (§5). Python's
   standard library has no YAML reader.

The repository's rule is that a new dependency needs an ADR. This one records two: a container
image and a Python package. No metric is involved, so there is no ledger entry.

The numbering: the design note assigns ADR-0002 to 0006 to other Phase 1 tasks (§9, "ADRs in
P1"), so this is 0007.

## Prior: what you expect each option to measure, before measuring (bake-offs and triggers)

There was no bake-off, and no prior was written down before the work, so none is claimed.

## Options considered: each with cost, risk, ops burden, and the trigger that would change the answer

**How the SQL tests reach a database.**

| Option | New dependencies | Why not, or why |
|---|---|---|
| pytest runs the `docker` command line, `psql` inside the container, and the dbmate that mise already pins | One image pin | **Chosen.** pytest and dbmate are already pinned; `psql` ships in the image. The tests check a schema, so rows coming back as JSON through `psql` are enough |
| The Testcontainers library with psycopg | Two Python packages and what they pull in | This is what the plan and the design note name for CI (§9, task 5) and for the kernel's property tests (§7.7). Those tests step several connections through transactions from Python and do need a driver. Task 8's do not |
| pgTAP | An extension inside the image, so an image of our own, and `pg_prove` | Needs the custom image that task 7 has not built yet |
| A PostgreSQL installed on the machine | None in the repository | Not pinned and not the same on CI. The owner's Mac has one of unknown version |

Trigger to revisit: task 10 brings Testcontainers and psycopg for the kernel's property tests,
with its own ADR. The schema tests can then share its fixtures, or stay as they are; they do
not block either choice.

**Which image.** The official `postgres` image, tag `18.6-trixie`, pinned by the digest of its
multi-platform index:

`postgres:18.6-trixie@sha256:e3d24f6906d0760bf4da0dae872415391ededefad23fd471c47dc53b0ddf3c42`

- The index covers `linux/amd64` and `linux/arm64/v8` (read with
  `docker buildx imagetools inspect` on 2026-11-15), so one pin serves both node architectures
  and CI.
- 18.7 exists, but it was released on 2026-11-12 (postgresql.org's release notes), which is
  inside the 7-day cooldown that ADR-0001 sets for dependencies. 18.6 was released on
  2026-08-13, and this build of its image was pushed on 2026-11-06 (Docker Hub's tag list,
  read on 2026-11-15). Move to 18.7 once it is a week old.
- Debian, not Alpine: it is the image's default variant. Which base the production image uses
  is task 7's decision.

Trigger to change: task 7 builds the production image (PostgreSQL 18 with its extensions).
From then on the SQL tests should run against that image, so that there is one PostgreSQL pin
and not two. The tests already take the image from `GL_TEST_PG_IMAGE` when it is set.

**How `prov/sources.yml` is read.**

| Option | Why not, or why |
|---|---|
| PyYAML 6.0.3, `yaml.safe_load` only | **Chosen.** MIT licence; released 2025-09-25; wheels for CPython 3.13 on macOS arm64 and on Linux x86-64 and aarch64 (PyPI's release list, read 2026-11-15). pyright's bundled stubs type it |
| ruamel.yaml | Its extra is writing YAML back with comments kept, which nothing here does |
| Keep the data as JSON or TOML, which the standard library reads | The plan names the file `prov/sources.yml`, in the text that is this repository's `CLAUDE.md`, and task 17 builds `/attributions` from the same file |
| A reader of our own for the part of YAML the file uses | A home-made parser in front of the licence table is a risk, not a saving |

Trigger to change: the plan renaming the file to a format the standard library reads.

## Decision: exactly one choice

Add two dependencies and no others:

- **For tests only, the image** `postgres:18.6-trixie` at the digest above. The SQL tests
  (`db/tests/pg`) start one throwaway container per run, prepare each database with
  `db/roles.sql` as the cluster's superuser, run dbmate as the role `migrator`, and query
  through `psql` inside the container.
- **As a development dependency, PyYAML 6.0.3**, used by `db/seedgen.py` with `safe_load`.

`mise run test` now runs the SQL tests after the unit tests, and `mise run test:db` runs them
alone. Both need Docker. `mise run check` does not: the Stop hook runs it at every turn end,
so it keeps to what needs no container. The checks on the migration that need no database
(the seed matches its sources; the file's text) are unit tests in `db/tests/unit` and do run
under `check`.

## Evidence: bench/eval/bake-off links; pre-registration; prior vs measured

Run on the owner's Mac (Apple M3 Pro, Docker Desktop 29.7.2) on 2026-11-15:

- `mise run test:db` passes: `dbmate up` applies `0001` to a clean PostgreSQL 18.6 as
  `migrator`; down and then up applies again; the tests of the task's list pass (the stamp
  check, the state enum, the primary keys, the partial index, both seeds, the grants).
- The tests can fail. Fifteen copies of the migration, each broken in one way (the check
  removed, the grid changed to 5 minutes, a state added, the states reordered, the index made
  whole, a column added, a grant widened, a seed row changed, a `drop` left out of the down
  section, and so on), were each run against the SQL tests, and each one failed them.
- pyright in strict mode reports no error in `db/`, with PyYAML typed by the stubs pyright
  carries.

Not verified: the tests on `linux/amd64` (the Mac is arm64, and CI does not exist yet); the
tests against any image but this one.

## Consequences: what gets easier/harder; rollback plan; what we will measure next

**Easier.** A migration is tested the way it runs in production: by dbmate, as a role that is
not a superuser, on the server version we deploy. Later migrations add a test file beside the
first.

**Harder.** `mise run test` now needs Docker running, and it fails without it; it does not skip.
The first run on a machine pulls the image.

**A second pin until task 7.** The image is named in one place, `db/tests/pg/test_0001_ingest.py`.
When task 7 pins the production image there will be two until the tests are pointed at it.
Renovate (task 5) has to be told about the pin in the test file, because it is not in a
Dockerfile or a Compose file.

**Departure from the design note's wording.** The note says "SQL tests in Testcontainers" for CI
(§9, task 5). These tests use a container without the Testcontainers library. CI can run them
as they are, with `mise run test:db`, on any runner that has Docker.

**Rollback.** Remove `db/tests/pg` and the `test:db` task to drop the image. Remove PyYAML from
the `dev` group and `db/seedgen.py` with it; the seed rows in the migration stay valid SQL.

**Next.** Task 5 runs `mise run test:db` in CI on both architectures. Task 7 replaces the pin
with the production image. Task 10 decides whether the schema tests move onto its fixtures.
