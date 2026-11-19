-- The three database roles of Phase 1 (docs/design/p1.md §5). No service is a superuser.
--
--   migrator   owns the database and runs dbmate: the only role that may run DDL
--   worker     reads and writes the ingest tables (poller, tier-1 workers, publisher)
--   readonly   reads, for building /stats
--
-- Roles belong to the cluster, not to a database, so no migration creates them. This file does.
-- Run it once per cluster as its initial superuser, connected to the application database,
-- before the first `dbmate up`:
--
--   psql -v ON_ERROR_STOP=1 -U postgres -d <database> -f db/roles.sql
--
-- It is safe to run again. It sets no password: a role created here cannot log in over the
-- network until the node's bootstrap gives it one from the secrets store (Phase 1 task 7).
-- What each role may touch is granted by the migrations, table by table.

-- The last statement below gives the connected database to migrator, so refuse the databases
-- that belong to the cluster itself.
do $$
begin
  if current_database() in ('postgres', 'template0', 'template1') then
    raise exception 'db/roles.sql must be run in the application database, not in %',
      current_database();
  end if;
end
$$;

do $$
begin
  if not exists (select from pg_roles where rolname = 'migrator') then
    create role migrator;
  end if;
  if not exists (select from pg_roles where rolname = 'worker') then
    create role worker;
  end if;
  if not exists (select from pg_roles where rolname = 'readonly') then
    create role readonly;
  end if;
end
$$;

-- Stated on every run, so a role that already existed ends up the same as a new one.
alter role migrator login nosuperuser nocreatedb nocreaterole noreplication nobypassrls;
alter role worker   login nosuperuser nocreatedb nocreaterole noreplication nobypassrls;
alter role readonly login nosuperuser nocreatedb nocreaterole noreplication nobypassrls;

-- So that dbmate needs no superuser: the owner of a database may create schemas in it, and may
-- create dbmate's own table, schema_migrations, in the schema `public`.
do $$
begin
  execute format('alter database %I owner to migrator', current_database());
end
$$;
