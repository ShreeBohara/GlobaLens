-- migrate:up

-- The ingest ledger and the provenance table: all of Phase 1's data model
-- (docs/design/p1.md §5, with the owner's decisions Q12, Q13 and Q14 from its §13 C).
--
-- dbmate runs this as the role `migrator`, which then owns everything created here. The roles
-- themselves are created by db/roles.sql before the first `dbmate up`.
-- Left out on purpose: `lease_epoch` and `ingest.dead_letter`. Both arrive in Phase 2.

create schema ingest;
create schema prov;

create type ingest.stream as enum ('english', 'translated');
create type ingest.state  as enum
  ('listed', 'fetched', 'verified', 'loaded', 'published',  -- the plan's chain
   'gap',                                                   -- never arrived within 7 days
   'dead');                                                 -- Q12: unusable file, needs a person

-- The fenced ledger: one row per 15-minute file of each stream. It is also the job queue.
create table ingest.interval (
  stream          ingest.stream not null,
  stamp           timestamptz   not null,          -- the 15-minute stamp, UTC
  url             text          not null,
  size            bigint,                          -- from lastupdate or the master list
  md5             text,
  state           ingest.state  not null default 'listed',
  attempts        int           not null default 0,
  next_attempt_at timestamptz   not null default now(),   -- per-file backoff
  lease_token     uuid,                            -- the fence: every commit names it
  lease_until     timestamptz,
  seq             bigint,                          -- Q13: set by the publisher, in publish order
  rows            int,
  raw_key         text,
  parquet_key     text,
  listed_at       timestamptz   not null,          -- knowledge time of the file
  loaded_at       timestamptz,
  published_at    timestamptz,
  last_error      text,                            -- Q12: why the file is `dead`, or last failed
  constraint interval_pkey primary key (stream, stamp),
  constraint interval_stamp_check
    check (stamp = date_bin('15 minutes', stamp, timestamptz 'epoch'))
);

-- What a tier-1 worker looks through when it takes a lease: the states it may claim.
create index interval_next_attempt_at_idx on ingest.interval (next_attempt_at)
  where state in ('listed', 'fetched', 'verified');

comment on table ingest.interval is
  'The ingest ledger: one row per 15-minute GDELT file per stream, walked from listed to published. Also the job queue (docs/design/p1.md §7).';
comment on column ingest.interval.lease_token is
  'Random token written when a worker takes the lease. A commit succeeds only if it names the current token.';
comment on column ingest.interval.seq is
  'Set by the publisher when the interval is published, in publish order. Null until then.';

-- Runs of files that GDELT never published, so that nothing waits for them.
create table ingest.known_gap (
  stream      ingest.stream not null,
  first_stamp timestamptz   not null,
  last_stamp  timestamptz   not null,              -- the last missing stamp, inclusive
  intervals   int           not null,
  reason      text          not null,
  recorded_at timestamptz   not null default now(),
  constraint known_gap_pkey primary key (stream, first_stamp)
);

comment on table ingest.known_gap is
  'Runs of 15-minute files that never arrived. first_stamp and last_stamp are both missing stamps; intervals counts them.';

-- One row per upstream dataset. The source of truth is prov/sources.yml.
create table prov.source (
  source_id        text primary key,
  licence          text    not null,
  redistribute_ok  boolean not null,
  share_alike      boolean not null,
  nc               boolean not null,
  attribution_text text    not null,
  verified_on      date    not null
);

comment on table prov.source is
  'One row per upstream dataset, with its licence. Generated from prov/sources.yml; never edited in place.';

-- Q14: one row per publishing pass.
create table ingest.publish_pass (
  seq          bigint primary key,     -- the value written to now.json
  manifest_key text,
  started_at   timestamptz not null default now(),
  finished_at  timestamptz,
  objects      jsonb                   -- writes per object class, against the Class A budget
);

comment on table ingest.publish_pass is
  'One row per publishing pass. seq is the pass number written to now.json; a crashed pass leaves a gap and the number is never reused.';

-- Roles (design note §5). `migrator` owns all of the above and needs no grant. The ledger is
-- never deleted from, so `worker` gets no delete. Only a migration writes prov.source.
grant usage on schema ingest to worker, readonly;
grant usage on schema prov   to readonly;

grant select, insert, update
  on ingest.interval, ingest.known_gap, ingest.publish_pass
  to worker;
grant select
  on ingest.interval, ingest.known_gap, ingest.publish_pass, prov.source
  to readonly;

-- Seeds. The rows between each pair of marker lines are written by db/seedgen.py and checked
-- against their sources by a test, so they are not edited here.

-- seed:begin ingest.known_gap (from the master-list script's output in db/seeds/known_gap/)
insert into ingest.known_gap
  (stream, first_stamp, last_stamp, intervals, reason)
values
  ('english', timestamptz '2025-06-14 18:00:00+00', timestamptz '2025-07-02 02:00:00+00', 1665, 'Never published by GDELT: the master file list has no gkg file for these stamps (list read up to 2026-11-16 01:00 UTC)'),
  ('translated', timestamptz '2025-06-14 17:45:00+00', timestamptz '2025-07-02 02:00:00+00', 1666, 'Never published by GDELT: the master file list has no gkg file for these stamps (list read up to 2026-11-16 00:45 UTC)');
-- seed:end ingest.known_gap

-- seed:begin prov.source (from prov/sources.yml)
insert into prov.source
  (source_id, licence, redistribute_ok, share_alike, nc, attribution_text, verified_on)
values
  ('gdelt-gkg-2.1', 'GDELT Terms of Use', true, false, false, 'Source: The GDELT Project (https://www.gdeltproject.org/)', date '2026-10-28'),
  ('natural-earth', 'Public domain', true, false, false, 'Made with Natural Earth', date '2026-10-28'),
  ('protomaps-basemap', 'ODbL-1.0', true, true, false, 'Protomaps © OpenStreetMap contributors', date '2026-10-28'),
  ('openfreemap', 'ODbL-1.0', false, true, false, 'OpenFreeMap © OpenMapTiles Data from OpenStreetMap', date '2026-10-28');
-- seed:end prov.source

-- migrate:down

drop table ingest.publish_pass;
drop table prov.source;
drop table ingest.known_gap;
drop table ingest.interval;
drop type ingest.state;
drop type ingest.stream;
drop schema prov;
drop schema ingest;
