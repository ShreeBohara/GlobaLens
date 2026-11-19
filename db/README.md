# db

SQL lives here and nowhere else. Migrations are dbmate files in `migrations/`, written
expand/contract: additive in the release that needs them, destructive one release later.

| Path | What |
|---|---|
| `migrations/0001_ingest.sql` | The ingest ledger (`ingest.interval`, `ingest.known_gap`, `ingest.publish_pass`) and `prov.source`: Phase 1's data model (`docs/design/p1.md` §5) |
| `roles.sql` | Creates the roles `migrator`, `worker` and `readonly`. Not a migration: see below |
| `seedgen.py` | Writes the seed rows of `0001` from their sources, and checks them |
| `seeds/known_gap/` | The master-list script's output behind the June 2025 seed, with the command |
| `tests/unit/` | Checks that need no database. Part of `mise run check` |
| `tests/pg/` | The SQL tests, against PostgreSQL 18 in Docker. Part of `mise run test` |

Still to come: the `Dockerfile` (PostgreSQL 18 with its extensions, Phase 1 task 7) and
`functions/` (with the first SQL function).

## Roles

No service connects as a superuser. Roles belong to the cluster, not to one database, so a
migration cannot create them without being a superuser itself. `roles.sql` creates them
instead. It is run once per cluster, as the cluster's initial superuser, before the first
`dbmate up`; it sets no password and is safe to run again. The node's bootstrap (task 7) runs
it and gives each role its password from the secrets store.

| Role | May |
|---|---|
| `migrator` | Run DDL. It owns the database and everything the migrations create. dbmate connects as this role |
| `worker` | Select, insert and update in the three `ingest` tables. No delete: ledger rows are never removed |
| `readonly` | Select from all four tables |

Each migration grants what its own tables need, by name.

## Running the tests

```bash
mise run test:db
```

This starts one throwaway PostgreSQL 18 container (the image is pinned by digest in
`tests/pg/test_0001_ingest.py`; `docs/adr/0007-sql-tests-and-yaml.md` says why that one), runs
`roles.sql`, applies the migrations with dbmate as `migrator`, and removes the container. It
needs Docker running and fails without it. `mise run test` runs the same tests after the unit
tests. `mise run check` never needs Docker.

If a run is killed, its container can be left behind. Remove any with:

```bash
docker ps -aq --filter label=globalens.sqltest=1 | xargs docker rm -f -v
```

## The seeds in `0001`

Two tables are seeded by the migration, and neither seed is typed by hand:

- `prov.source` comes from [`prov/sources.yml`](../prov/sources.yml), the source of truth for
  upstream datasets and their licences.
- `ingest.known_gap` comes from the saved output of the master-list script
  ([`seeds/known_gap/`](seeds/known_gap/README.md)).

The rows sit in the migration between `-- seed:begin <table>` and `-- seed:end <table>` lines.

```bash
uv run --no-sync python db/seedgen.py check
```

exits with 1 and prints the difference when the migration and a source disagree; a unit test
runs it, so `mise run check` catches the drift. To rewrite the rows from the sources:

```bash
uv run --no-sync python db/seedgen.py write
```

**Once `0001` has been applied to production its text is frozen.** After that, a change to
`prov/sources.yml` goes into a new migration, and the unit test that compares `0001` with the
whole file has to learn to add the later migrations up. That work belongs to the task that
adds the next source. The SQL test that compares the migrated table with `prov/sources.yml`
stays true through it.

## Writing a migration

- One file per change, `NNNN_name.sql`, with `-- migrate:up` and `-- migrate:down`.
- The down section drops exactly what the up section creates, without `cascade`.
- No `create role` and no password in a migration.
- dbmate's schema dump is off in the tests (`--no-dump-schema`): no `schema.sql` is committed.
