# GlobaLens 3.0: Backend and Data Architecture (research as of 2026-10-28)

**Scope.** Backend for a real-time news-intelligence system: one builder, about $50/month, designed to scale. Facts checked online in October 2026. Confidence tags: **[H]** high, **[M]** medium, **[L]** low/unverified. The web-search budget ran out late in the session, so [L] items come from memory or a single third-party source; verify before relying on them.

## TL;DR

- **Writes are small; reads are hard.** GDELT 2.0 publishes about 10.5 MB zipped every 15 minutes (about 1 GB/day, roughly 1M rows/day). One Postgres absorbs that easily. The real problems: map/time/filter reads in under 300 ms over tens of millions of points, vector RAM, multi-year analytics, multilingual text, and correctness (idempotency, feed gaps, backfills).
- **Core:** self-hosted PostgreSQL 18 with PostGIS, h3-pg, pgvector, pg_partman and pgmq, plus an immutable Parquet lake on Cloudflare R2. **The raw GDELT files are our replay log, so Kafka isn't needed for replay.**
- **Add components only when a measured trigger fires** (§9): Dagster OSS → pgmq worker pools → NATS JetStream with SSE → Martin tiles and a Rust parser → ClickHouse → VectorChord or Qdrant.
- **Avoid:** Kafka/Redpanda/Flink (padding at about 15 msg/s), Dagster+ credits (about $576/mo here), managed Postgres for vectors (3–4× cost per GB of RAM), Kuzu (archived), Bytewax (abandoned **[corrected: the company folded in 2025 and nothing has been released since v0.21.1, but a community-maintained restart began in May 2026. It is still too immature to use]**), TimescaleDB (TSL license, provider churn). Product flags in §10.

## 1. Workload reality check (measured)

GDELT batch file sizes, 2026-10-29 (English 06:00 UTC, translingual 05:45 UTC) **[H]**:

| File | English | Translingual |
|---|---|---|
| events export (zip) | 50 KB | 58 KB |
| mentions (zip) | 65 KB | 60 KB |
| GKG (zip) | 3.18 MB | 7.12 MB |

- **Volume:** about 10.5 MB per batch × 96 ≈ **1 GB/day, 30 GB/month raw**. This is one sample; measure for a week. **[fact-check: a second sample (English 06:15, translingual 06:00 UTC on 2026-10-29) totals 12.5 MB, with GKG at 4.23 + 8.06 MB. Budget 1.0–1.2 GB/day]**
- **Rows (estimated from sizes) [M]:** events 100–200k/day, mentions 200–400k/day, GKG 100–400k/day. Total ≈ **1M rows/day**: about 12 rows/s on average, with ~10k-row bursts every 15 minutes. `COPY` loads a batch in about a second.
- **GKG is ~98% of bytes**, mostly the GCAM field. **Never put raw GKG in Postgres.** Land it as Parquet (zstd) and project the ~15 columns we use.
- **GDELT is shrinking [M, zipped size as proxy].** Weekday daily event export: 15–16 MB (Oct 2015) → 11–13 MB (2017–19) → 9.8 MB (2024) → 8.4 MB (2025) → 7–7.6 MB (Oct 2026). **[fact-check: the index shows 15.3–15.8 MB for Oct 13–16, 2015, 8.6 MB for 2025-10-15 and 7.4–8.0 MB on Oct 2026 weekdays, so the halving holds]**

**Implication:** write volume never justifies distributed infrastructure. Spend the complexity on read models, RAM-efficient vectors, history analytics, multilingual NLP and correctness.

## 2. Streaming backbone (a)

| Option (Oct 2026) | Status, license | Solo ops burden | Cost at our scale | Verdict |
|---|---|---|---|---|
| Postgres outbox + **pgmq** | PostgreSQL License, PG 14–18; visibility timeouts, archive, FIFO groups **[H]** | ~zero (lives in the DB) | $0 | **Default for Phases 1–4** |
| **NATS JetStream** | Apache-2.0; stayed in CNCF after the May 2025 Synadia settlement (trademark → Linux Foundation) **[H]** | One Go binary, tiny RAM; streams, KV, object store, WebSockets, `Nats-Msg-Id` dedup | $0 self-hosted | **Pick for fan-out and live push** |
| Kafka 4.2 (KRaft) | No ZooKeeper since 4.0; share groups (queues) production-ready Feb 2026 **[H]** | JVM, partitions, tuning | $0 self / $$ managed | Overkill |
| Redpanda | BSL **[M]**; 2025 Serverless ≈$0.10/h base + $0.045/GB in **[L]** | One binary, RAM-hungry | ≈$70+/mo floor **[L]** | Overkill |
| Valkey Streams | BSD (Valkey 9) | Another stateful store, memory-bound | $0 | Only if Valkey already runs |
| GCP Pub/Sub | $40/TiB after 10 GiB free **[H]** | None | ≈$0 | OK if all-in on GCP; weak for local dev |

**Opinion:** a broker earns its place once **three or more independent consumers** need the same events (DB writer, embedder, story clusterer, alert engine, live gateway, lake archiver). That arrives around Phase 5, and JetStream is the right size for it. Kafka's queue semantics are irrelevant at ~10 msg/s. If Kafka matters for the resume, show it in a benchmark appendix, not in production.

## 3. Orchestration and stream processing (b)

| Tool | 2026 status | Fit |
|---|---|---|
| **Dagster OSS** | 1.13.x; Components and `dg` CLI GA (1.11.10+). **Prefect is acquiring Dagster Labs (announced 2026-07-13)**; Dagster keeps its name, OSS license and roadmap **[H]** **[corrected: both announcements commit to the Dagster name and roadmap but say nothing about the license. dagster 1.13.27 (2026-10-26) is still Apache-2.0. Neither announcement says the deal has closed]** | **Best fit.** 15-min time-window partitions, sensors, backfills, asset checks, lineage. Self-host it |
| Dagster+ | Solo $10/mo + $0.040/credit; 1 credit = 1 asset materialization or op **[H]** | 96 batches/day × 5 assets × 30 days ≈ 14.4k credits ≈ **$576/mo**. No |
| Airflow 3.2 | Apr 2026: asset partitions and partition mappers; 3.3.x out **[H]** | Strong keyword but heavier (scheduler, API server, dag-processor, triggerer). Fallback |
| Prefect 3 | Now Dagster's parent **[corrected: the announced acquirer; no closing confirmed as of 2026-10-28]**; also maintains FastMCP | Fine for flows; weaker asset/partition model |
| Temporal | Cloud pricing in flux, ≈$50/M actions **[L]** | Overkill. Revisit only for long multi-step agent jobs |

**Stream processors are overkill for 15-minute micro-batches;** running SQL once per batch gives identical results.
- **Flink 2.x:** a heavy JVM cluster.
- **RisingWave 3.0:** GA June 2026, Apache-2.0 **[M]**. The only one worth a look, and only if we add a true firehose source.
- **Materialize:** BSL. Community Edition capped at 24 GiB memory / 48 GiB disk with a yearly key **[M]**.
- **Arroyo:** acquired by Cloudflare in April 2025 for its Pipelines product **[H]**.
- **Bytewax: avoid.** The company was "no longer commercially viable" from May 2025; no release since v0.21.1 (Nov 2024) **[H]**. **[corrected: the project isn't fully abandoned. After the company folded (May 2025), a community-maintained Apache-2.0 restart began in May 2026, with about 24 PRs merged and v0.22.0rc1 planned. Nothing has been released after v0.21.1, so the verdict stands]**

## 4. Databases (c)

### 4.1 Postgres core (pick)
- **PostgreSQL 18** (GA 2025-09-25) **[H]**. Useful features:
  - async I/O for scans and vacuum
  - `uuidv7()` time-ordered IDs
  - B-tree skip scan
  - virtual generated columns
  - temporal `WITHOUT OVERLAPS`
  - `RETURNING OLD/NEW`
  - `pg_upgrade` keeps statistics
- **PG19 reached RC1 on 2026-10-15** **[H]**. Upgrade in a later phase once extensions certify; it makes a good drill. SQL/PGQ is reportedly pulled from 19 **[L]**.
- **Extensions (as shipped for PG18):**
  - PostGIS 3.6.x, h3/h3_postgis 4.2.3 **[H]**
  - pgvector **≥0.8.7**
  - pg_partman 5.x, pg_cron, pgmq 1.10 **[M]**
  - optional: pg_ivm 1.17 (Oct 2026)
- **Drop MongoDB Atlas.** The workload is relational, geospatial and aggregate-heavy, and SQL gives the agent a safer, inspectable query surface.

### 4.2 Vectors
- **pgvector 2026 [H]:**
  - 0.8.2 fixed a parallel-HNSW-build overflow.
  - **0.8.7 (2026-10-01) fixes an IVFFlat-build CVE.** **[fact-check: CVE-2026-103484, an IVFFlat-build buffer overflow that can allow arbitrary code execution. Neon's 0.8.6 (below) predates the fix]**
  - 0.9.0 (unreleased) adds async I/O for HNSW and drops PG 13/14.
  - Managed providers lag: Neon's PG18 ships 0.8.6.
- **RAM math** (raw bytes per vector; HNSW adds graph overhead):

| Representation | Bytes/vec | 1M vectors | 14-day hot window at 200k/day (2.8M) |
|---|---|---|---|
| vector(768) fp32 | 3,072 | 3.1 GB | 8.6 GB ✗ |
| halfvec(768) | 1,536 | 1.5 GB | 4.3 GB |
| halfvec(384), MRL-truncated | 768 | 0.77 GB | 2.2 GB ✓ |
| bit(768) binary-quantized index, with re-rank | 96 | 0.1 GB | 0.27 GB ✓✓ |

- **Pattern:**
  - Index `binary_quantize(emb)` (or halfvec) with HNSW, per daily partition, for the hot window only.
  - Re-rank the top k×10 at full precision; use iterative scans (0.8.0+) for bbox/time/language filters.
  - **Drop partitions instead of `DELETE`.** HNSW vacuum is costly, and its repair/corruption bugs were only fixed in 0.8.3–0.8.4.
  - Older vectors go to Parquet; use DuckDB or LanceDB for "search all history".
- **Scale-up:**
  - Prefer **VectorChord 1.1.x**: IVF + RaBitQ, 4/8-bit types, AGPLv3/ELv2. The vendor claims much faster index builds **[M]**.
  - pgvectorscale 0.9 (Nov 2025) is still "early stage" **[M]**.
  - Qdrant if we leave Postgres. Milvus is overkill.

### 4.3 Hybrid search (BM25 + vectors)
- **Start in Postgres:** `tsvector` (`simple` + `unaccent`, plus English-normalized GKG themes and entities) fused with pgvector via Reciprocal Rank Fusion in one SQL statement. No new infrastructure.
- **ParadeDB pg_search** (true BM25, AGPL, v0.26.x as of Oct 2026) **[H]**: good only if self-hosting.
  - **Neon removed it** (deprecated 2026-03-19, retired 2026-09-21), a real portability risk on managed Postgres.
  - One benchmark reports a 0.26 single-term query regression **[L]**.
- **Qdrant 1.20 (2026-10-22)** ranks BM25 directly on stored text and runs dense search in the same engine **[M]**. Free cloud cluster: 1 GB RAM / 4 GB disk, suspends after a week idle. Best engine to graduate to.
- **Not needed [H]:** Meilisearch (CE MIT; EE under BUSL since v1.19, Aug 2025), Typesense (GPL-3), OpenSearch (heavy JVM).

### 4.4 Time series
- **Skip TimescaleDB.** 2.30 (Sept 2026) is excellent, but hypercore and continuous aggregates are **TSL (not OSI)**, and **Supabase dropped Timescale on PG17** **[H]**.
- **Our series are low-cardinality aggregates** (time bucket × H3 cell × theme). Use pg_partman partitions, BRIN on time, and idempotent per-batch rollup upserts (pg_ivm optional).

### 4.5 Analytics and lake
- **DuckDB 1.5** (2026-03-09) adds a built-in GEOMETRY type. **DuckLake 1.0** (2026-04-13) **[H]** supports:
  - Postgres, SQLite or DuckDB catalogs
  - partitioning and compaction
  - inlining of small inserts
  - Iceberg-compatible bucket transforms
  - readers in DataFusion, Spark and Trino
- **Plan:** use our Postgres as the DuckLake catalog and keep Parquet on R2 ($0.015/GB-month, 10 GB free, $0 egress). Zero idle cost. Time travel enables "rewind the world". Compact daily, or each table collects 96 files/day.
- **ClickHouse (self-host when triggered):**
  - vector index GA since 25.8 (HNSW; bf16/i8/b1); QBit type in 25.10 **[H]**
  - mature H3/geo functions; reads Parquet from R2
  - ClickHouse Cloud Basic is over budget: worked example $66.52/mo (2 vCPU, 8 GiB, 6 h/day), about $186/mo 24/7.
- **Skip full Iceberg** unless several engines must share tables.
- **BigQuery's GDELT public dataset** is good for one-off historical exploration, but GKG scans burn the free tier fast **[M]**.

### 4.6 Graph
- **Kuzu: avoid.** Archived October 2025; the last release named is 0.11.x; a community fork exists (Kineviz "bighorn") **[H]**. Apple-acquisition reports are unverified **[L]**.
- **Others:** Apache AGE is active again (v1.7.0, 2026-01-21, with a PG18 build) **[H]**. FalkorDB is SSPL **[H]**; Memgraph is BSL **[L]**.
- **Pick:** `entity`, `mention` and `edge(src, dst, kind, bucket, weight)` tables, with recursive CTEs for 1–2-hop neighborhoods. Run PageRank and community detection offline in Dagster (igraph/DuckDB). Add AGE only for a Cypher showcase.

### 4.7 Cache
- **Options:** Valkey 9 (BSD; JSON, Bloom and search modules) **[H]**, Redis 8 (adds an AGPL option) **[M]**, Dragonfly (BSL) **[M]**.
- **Start without one:** CDN + HTTP caching + Postgres. Add Valkey for cross-process rate limiting or hot-key contention.

## 5. API layer (d)
- **FastAPI** (0.162.0, 2026-10-23). Its docs now cover native SSE (`EventSourceResponse`), JSON Lines streaming and OpenTelemetry **[M]**. Largest ecosystem, closest to ML tooling. **Pick it.**
  - Litestar (msgspec) is excellent, but 3.0 is still unreleased (target Q3–Q4 2026).
- **Contract:** OpenAPI 3.1 → TypeScript client via **@hey-api/openapi-ts** (TanStack Query + Zod plugins) or **orval**. CI fails when the spec and client drift.
  - tRPC only fits a TypeScript backend.
  - Hono only as an optional edge BFF.
- **Connect/gRPC:** connect-python is still beta (0.13) **[M]**, so not for the public API. **Do** use protobuf + `buf breaking` for internal event envelopes (NATS payloads).
- **GraphQL: no.** One first-party client; caching cost and N+1 risk.
- **Live updates: SSE first.**
  - Postgres `LISTEN/NOTIFY` takes a global lock at commit under many writers. That caused outages at Recall.ai in March 2025; the article says a core fix has since landed **[H]**.
  - Fine for 96 batch commits/day, but not as the fan-out backbone. Later, put NATS in front of an SSE gateway.
- **Safe agent access, three layers:**
  1. An MCP server (e.g., FastMCP) exposes **typed tools** over the read models: `search`, `lens(center, radius, time)`, `timeseries`, `story`, `entity_neighbors`. No raw SQL on production.
  2. Ad-hoc analysis runs in a **DuckDB sandbox over a DuckLake snapshot**: read-only, memory/time limits, external access off, SELECT-only validated by sqlglot, row caps.
  3. Optional Postgres SQL goes to a replica: an `agent_ro` role with read-only transactions and `statement_timeout`, `api`-schema views plus RLS, and every query audited.

## 6. Rust and C++ (e): justified vs padding

| Candidate | Verdict | Evidence required first |
|---|---|---|
| GKG nested-field parser (V2Locations, GCAM, themes) as a PyO3/maturin wheel emitting arrow-rs | **Justified** for the 10-year backfill (several TB zipped) | Beats a Polars/pyarrow baseline by ≥5× and is needed for a stated goal (e.g., 10 years in under 24 h on one box) |
| Vector tile server | **Use Martin** (Rust; 2.0.0-beta.5, Oct 2026; PostGIS function sources, PMTiles, always-on MLT) **[H]** | None |
| Binary lens/time-cube endpoint (Arrow IPC for deck.gl) | Probably not; pyarrow already runs in C++ | p95 serialization above 100 ms |
| H3 in WASM via h3o (pure Rust, BSD-3), shared by browser and server | Nice to have; honest "shared core" story | h3-js exists, so justify with lens-fill parity tests |
| Custom C++ extensions or indexes | **Padding** | None |

**Crates:** tokio, axum, arrow-rs/parquet, polars, h3o (0.9.x), geo, geozero, plus PyO3/maturin bindings. Versions not pinned here **[M]**.

## 7. Scale patterns (f), applied to GlobaLens
- **Immutable raw log.** Every GDELT file goes to R2 under `raw/yyyy/mm/dd/hhmm/` with its MD5 from `lastupdate.txt`. Everything downstream is rebuildable: event sourcing without Kafka.
- **Ingestion ledger.** A `batch` table (`batch_ts` key, md5, status, row counts) plus a gap detector that computes the expected 15-minute timestamps and fetches missing ones. GDELT has outages.
- **Idempotency:**
  - Natural keys: `GLOBALEVENTID`, `(GLOBALEVENTID, MentionIdentifier)`, `GKGRECORDID`.
  - Staging + `MERGE` / `ON CONFLICT DO NOTHING`.
  - At-least-once consumers behind unique constraints.
  - Transactional outbox plus JetStream `Nats-Msg-Id` dedup for publishers.
- **Partitioning and tiering:**
  - Daily partitions via pg_partman.
  - BRIN on time, GiST on geometry, B-tree on H3.
  - Keep 30–90 days hot in Postgres; detach older partitions to Parquet/DuckLake.
- **H3 keys.** Store the res-8/9 cell as BIGINT at ingest. Roll up by `(bucket, res, cell, cameo_root/theme, lang)` for res 2–7, so the zoomed-out globe needs only a few thousand cells.
- **Per-batch rollups** in the same transaction as the load: deterministic and replayable, no streaming aggregation needed.
- **CQRS.** Write model (events, articles, entities) vs read models (hex rollups, story timelines, search index, tile functions). All read models are rebuildable from the lake.
- **Immutable buckets → CDN.** A closed 15-minute or hourly bucket never changes. Serve its tiles and rollups with `Cache-Control: immutable`; only "now" stays dynamic. Huge read scale for $0.
- **Separate backfill and live lanes.** Dagster partition backfills go GDELT → Parquet → ClickHouse in bulk and never touch the live path.
- **Evolution:**
  - protobuf + `buf breaking` for events
  - explicit Parquet schemas
  - `embedding_model`/`version` columns on vectors
  - dual-write plus a Dagster re-embed backfill when the model changes

## 8. Monthly cost (g)

| Component | Self-hosted | Managed (Oct 2026 list) |
|---|---|---|
| VM | Hetzner after 2026-06-15, ex-VAT **[M]**: CPX32 (4 vCPU / 8 GB) **€35.49**; CPX42 (8 vCPU / 16 GB) €69.49; CCX13 (2 dedicated / 8 GB) €42.99. "Cost-Optimized" CX/CAX **can't currently be ordered** **[fact-check: confirmed for Germany/Finland, but these prices exclude the primary IPv4. Hetzner's product pages list €35.99 / €69.99 / €43.49 with IPv4. US sites cost far more (e.g., CPX31 at 4 vCPU / 8 GB is €62.99), so the budget assumes an EU VM]** | — |
| Postgres | On the VM | Supabase **[H]**: Pro $25 incl. Micro (1 GB); Medium (4 GB) $60; Large (8 GB) $110; disk $0.125/GB. Neon Launch: $0.106/CU-h (≈4 GB/CU **[M]**) + $0.35/GB-month |
| Orchestrator | Dagster OSS $0 | Dagster+ Solo ≈ $576 at 15-min partitions |
| Broker | NATS $0 | Pub/Sub ≈ $0 (<10 GiB); Redpanda Serverless ≈ $70+ **[L]** |
| Analytics | ClickHouse on the VM $0 | ClickHouse Cloud: $66.52 (6 h/day) to $186 (24/7) |
| Lake | — | R2 ≈ $1–3 |
| Vector DB | In Postgres $0 | Qdrant Cloud free tier (1 GB RAM), demos only |
| Frontend and CI | — | Vercel Hobby / Cloudflare free; GitHub Actions free for public repos **[M]**. Cloud Run free tier: 180k vCPU-s, 360k GiB-s, 2M requests **[M, not re-verified]** |

- **Lean self-hosted (Phases 1–6): ≈ $42–48/mo** (CPX32 + R2 + domain).
- **Scaled self-hosted (Phases 7–10): ≈ $80/mo** (CPX42 with ClickHouse and a bigger vector window). Over target; mitigate by keeping history in DuckLake (zero idle cost) and running ClickHouse only once its trigger fires.
- **All-managed equivalent: ≈ $300–900/mo.** Self-hosting Postgres is the biggest cost lever.
- **2026 pricing context:** Hetzner raised cloud prices 30–37% in April 2026 and CPX/CCX 113–176% in June 2026, citing hardware costs. **[corrected: Hetzner documents one adjustment, effective 15 June 2026, which it attributes to sharply higher procurement prices. In Germany/Finland it raised CX/CAX by about 31–38% (e.g., CX23 €3.99 → €5.49) and CPX/CCX by about 144–173% (CPX32 €13.99 → €35.49; CCX13 €15.99 → €42.99). An April 2026 increase does not appear on Hetzner's pages and is unverified]** **RAM is the scarce resource**, so design for it: halfvec, binary quantization, MRL-truncated dimensions, hot windows.

## 9. Target architecture and incremental path

```
GDELT EN + translingual (every 15 min) ─► Ingest (Dagster sensor + ledger) ─► R2: raw zip + Parquet (DuckLake; Postgres catalog)
                                              │ COPY/MERGE (idempotent)
                                              ▼
              PostgreSQL 18 · PostGIS · h3 · pgvector · pg_partman · pgmq
              write model (events/articles/entities) ──► read models (H3 rollups · stories · search · tile fns)
                     │ outbox                                   ▲
                     ▼                                          │
       [P5] NATS JetStream ─► workers: fetch · embed · NER · cluster · alerts
                     ▼
       FastAPI (REST + SSE) · Martin (MVT/MLT) · MCP tools · DuckDB sandbox ─► CDN ─► Next.js globe/lens
       [P7+] ClickHouse (history, fed from Parquet) · [P8+] VectorChord / Qdrant
```

| Stage | Adds | Introduce when (measurable rule) |
|---|---|---|
| 0 | Postgres, FastAPI, one Python worker, R2 raw landing | Day 1 |
| 1 | Dagster OSS: partitions, sensors, asset checks, backfills | ≥3 dependent jobs or the first backfill (in practice, right after the first slice) |
| 2 | pgmq worker pools for fetch, embed, NER, cluster | A step needs its own retries, scaling or latency (fetch is flaky I/O; embedding is CPU-bound) |
| 3 | NATS JetStream + SSE gateway | ≥3 consumers of the same event, or live push to clients |
| 4 | Martin tiles; Rust GKG parser | >50k features per viewport or zoomable tiles needed; parsing >50% of batch time or the backfill goal missed |
| 5 | ClickHouse (self-hosted) | History ≈1B rows, or p95 >2 s for >90-day analytics despite rollups |
| 6 | VectorChord (or Qdrant) | >~10M hot vectors, HNSW >50% of RAM, or filtered recall@10 <0.95 |
| 7 | Read replica / Valkey | Agent or analytics load moves API p95, or cross-process rate limiting needed |

## 10. Product-direction flags
1. **Multilingual is the majority, not a feature.** Translingual GKG is about 2.2× English, and v1's English-only model ignored most of the world. Cross-lingual story clustering and comparing how each language's press frames a story is a strong signature capability.
2. **GDELT is alive but shrinking**, at about half its 2015 coded-event volume. Build ingestion around a source-connector interface and add a second source early.
3. **For GDELT, "real-time" means 15 minutes.** Invest in **time travel** (immutable 15-minute snapshots back to 2015) and **trust signals** (corroboration from `NumSources`/`NumArticles`, source diversity, geocoding confidence) rather than sub-second streaming.
4. **Metadata first.** Store titles, entities, embeddings and snippets, and link out. Never store full article text; v1 did, and that is a copyright exposure.
5. **To make streaming earn its place honestly,** add a truly real-time source such as hazard feeds or a social firehose **[L, not researched here]**.

## Recommendations for GlobaLens 3.0
1. **(Must) Postgres-first, self-hosted core.** PG18 + PostGIS 3.6 + h3 4.2.3 + pgvector ≥0.8.7 + pg_partman + pgmq on one VM, with an immutable GDELT landing zone on R2. Plan the PG19 upgrade as a later phase.
2. **(Must) Ledger-driven, idempotent ingestion:** MD5 checks, natural-key merges, gap backfill, and H3 rollups computed per batch as CQRS read models. Mark closed buckets immutable so the CDN can cache them.
3. **(Must) Multilingual from day one.** Ingest the translingual stream. Store MRL-truncated halfvec embeddings with a binary-quantized HNSW index over a hot window only. Drop partitions; don't delete rows.
4. **(Must) Self-host Dagster OSS** for partitioned assets, checks and backfills, never Dagster+ credits. Write an ADR on the Prefect-ownership risk, with Airflow 3.2 as the fallback.
5. **(Should) Hybrid search in Postgres** (FTS + pgvector + RRF). Graduate to Qdrant 1.20, or ParadeDB if self-hosted, only on measured relevance or latency gaps. Never depend on extensions that managed providers might drop.
6. **(Should) Live layer = FastAPI SSE fed by NATS JetStream**, with an outbox and Msg-Id dedup, introduced only once ≥3 consumers exist. No Kafka, Redpanda or Flink.
7. **(Should) Map stack = Martin + H3 rollups**, with Arrow time-cubes for time scrubbing. Build the Rust GKG parser (PyO3) only to hit a published backfill benchmark.
8. **(Should) Agent data plane:** MCP typed tools, a DuckDB/DuckLake sandbox, a read-only role with timeouts and RLS, and an audit log.
9. **(Could) ClickHouse, self-hosted, only when its trigger fires.** Until then, history lives in DuckLake on R2.
10. **(Could) Entity graph as Postgres edge tables** with offline analytics. Add AGE only for a Cypher showcase; avoid Kuzu and FalkorDB.
11. **(Must, process) An ADR for every component** with its trigger and a before/after benchmark. The resume story is the measured evolution, not the component count.

## Sources
- GDELT live update files (sizes and MD5s): http://data.gdeltproject.org/gdeltv2/lastupdate.txt ; http://data.gdeltproject.org/gdeltv2/lastupdate-translation.txt
- GDELT daily event file index (volume trend): https://data.gdeltproject.org/events/index.html
- pgvector changelog: https://github.com/pgvector/pgvector/blob/master/CHANGELOG.md ; 0.8.7 announcement: https://www.postgresql.org/about/news/pgvector-087-released-3392/
- PostgreSQL 18 release notes: https://www.postgresql.org/docs/18/release-18.html ; PG news archive (PG19 RC1, pg_ivm 1.17): https://www.postgresql.org/about/newsarchive/ ; PG19 feature churn (third-party): https://www.devx.com/cybersecurity/postgresql-19-new-features-release-date/
- Neon pg_search retirement: https://neon.com/docs/extensions/pg_search ; Neon extension versions: https://neon.com/docs/extensions/pg-extensions ; Neon plans: https://neon.com/docs/introduction/plans
- Supabase pricing: https://supabase.com/pricing ; Supabase PG17 removes TimescaleDB: https://supabase.com/changelog/35851-forthcoming-postgres-17-release-notes
- ParadeDB releases: https://github.com/paradedb/paradedb/releases
- VectorChord: https://pgxn.org/dist/vchord/ ; https://blog.vectorchord.ai/vectorchord-10-developer-first-vector-search-on-postgres-100x-faster-indexing-than-pgvector
- pgvectorscale: https://www.tigerdata.com/docs/reference/pgvectorscale
- TimescaleDB: https://www.tigerdata.com/docs/about/latest/changelog ; https://www.tigerdata.com/docs/about/latest/timescaledb-editions
- ClickHouse: https://clickhouse.com/docs/reference/engines/table-engines/mergetree-family/annindexes ; https://clickhouse.com/blog/clickhouse-release-25-10 ; https://clickhouse.com/docs/cloud/manage/billing/overview
- DuckDB 1.5: https://duckdb.org/2026/03/09/announcing-duckdb-150 ; DuckLake 1.0: https://ducklake.select/2026/04/13/ducklake-10/
- Kuzu archived: https://www.theregister.com/2025/10/14/kuzudb_abandoned/
- Apache AGE: https://age.apache.org/release-notes/ ; https://github.com/apache/age/discussions/2305
- FalkorDB license: https://docs.falkordb.com/license.html
- Qdrant 1.20: https://www.financialcontent.com/article/bizwire-2026-10-22-qdrant-120-simplifies-hybrid-search-by-ranking-keywords-directly-on-stored-text ; https://qdrant.tech/cloud/
- Meilisearch license: https://www.meilisearch.com/blog/enterprise-license ; https://meilisearch.com/docs/resources/self_hosting/enterprise_edition
- Valkey 9: https://aws.amazon.com/blogs/database/announcing-valkey-9-0-for-amazon-elasticache/ ; https://docs.cloud.google.com/memorystore/docs/valkey/release-notes
- Kafka 4.2: https://www.confluent.io/blog/apache-kafka-4-2-release/ ; https://kafka.apache.org/42/getting-started/upgrade/
- Redpanda Serverless (2025 rates): https://www.redpanda.com/blog/new-redpanda-serverless
- NATS/CNCF settlement: https://www.theregister.com/2025/05/02/cncf_synadia_nats/ ; https://www.cncf.io/blog/2025/05/01/protecting-nats-and-the-integrity-of-open-source-cncfs-commitment-to-the-community
- Pub/Sub rate (Google Eventarc pricing page): https://cloud.google.com/eventarc/pricing
- pgmq: https://github.com/pgmq/pgmq
- LISTEN/NOTIFY global lock: https://www.recall.ai/blog/postgres-listen-notify-does-not-scale
- Prefect acquires Dagster: https://dagster.io/blog/prefect-is-acquiring-dagster ; https://www.prefect.io/prefect-acquires-dagster ; Dagster pricing and credits: https://dagster.io/pricing ; Components GA: https://dagster.io/blog/dagster-components-ga
- Airflow 3.2: https://www.astronomer.io/blog/apache-airflow-3-2-release/ ; https://airflow.apache.org/docs/apache-airflow/stable/release_notes.html
- Temporal pricing (third-party, low confidence): https://automationatlas.io/answers/temporal-pricing-explained-2026/
- Arroyo to Cloudflare: https://blog.cloudflare.com/cloudflare-acquires-arroyo-pipelines-streaming-ingestion-beta/
- Bytewax status: https://github.com/bytewax/bytewax/issues/560
- RisingWave 3.0: https://risingwave.com/blog/announcing-risingwave-3-0-the-real-time-data-platform-for-agentic-ai/
- Materialize Community Edition: https://materialize.com/changelog/2025-03-11-materialize-self-managed-and-community-editions/ ; https://materialize.com/docs/self-managed/v25.2/release-notes/versioning_lifecycle/
- FastAPI release notes and docs: https://fastapi.tiangolo.com/release-notes/
- Litestar 3: https://litestar.dev/blog/v3-announcement/ ; https://litestar.dev/about/
- connect-python: https://github.com/connectrpc/connect-py/releases/tag/v0.13.0 ; https://pypi.org/project/connectrpc/
- OpenAPI TypeScript codegen comparison (third-party): https://www.pkgpulse.com/guides/orval-vs-openapi-typescript-vs-kubb-openapi-client-2026
- Martin tile server: https://maplibre.org/martin/changelog/ ; https://github.com/maplibre/martin
- h3-pg: https://cdn.jsdelivr.net/gh/postgis/h3-pg@main/README.md ; https://ubuntuupdates.org/package/postgresql/jammy-pgdg/main/base/postgresql-18-h3
- h3o: https://docs.rs/crate/h3o/latest
- Hetzner: https://www.hetzner.com/cloud/ ; https://northflank.com/blog/hetzner-cloud-server-price-increases
- Cloudflare R2 pricing: https://developers.cloudflare.com/r2/pricing/

## Fact-check (2026-10-28)

**Method.** Each claim below was checked on 2026-10-28/29 UTC against a primary source: an official page, changelog, release page or pricing page, or the GDELT files themselves. The shared web-search budget ran out early in this pass, so only known primary URLs were fetched. Claims with no primary page are marked unverified. Inline fixes are tagged **[corrected: ...]**; confirmations that add detail are tagged **[fact-check: ...]**.

| Claim | Verdict | Correction / note | Source |
|---|---|---|---|
| GDELT 2.0 ships 15-minute batches of ≈10.5 MB zipped (≈1 GB/day), GKG is ≈98% of bytes, and daily volume is about half of 2015 | Confirmed | Second sample (2026-10-29): 12.5 MB per batch (EN export 58 KB, mentions 84 KB, GKG 4.23 MB; translingual GKG 8.06 MB), so plan for 1.0–1.2 GB/day. Daily event export: 15.3–15.8 MB on Oct 13–16, 2015 vs 7.4–8.0 MB on Oct 2026 weekdays | [lastupdate.txt](http://data.gdeltproject.org/gdeltv2/lastupdate.txt), [lastupdate-translation.txt](http://data.gdeltproject.org/gdeltv2/lastupdate-translation.txt), [events index](https://data.gdeltproject.org/events/index.html) |
| PostgreSQL 18 went GA 2025-09-25 with AIO, `uuidv7()`, skip scan, virtual generated columns, `WITHOUT OVERLAPS`, `RETURNING OLD/NEW` and statistics kept by `pg_upgrade`; PG19 RC1 came out 2026-10-15 | Confirmed | All seven features are in the release notes, though `pg_upgrade` doesn't keep extended statistics. The note that SQL/PGQ was pulled from PG19 is still unverified | [PG18 release notes](https://www.postgresql.org/docs/18/release-18.html), [PG news archive](https://www.postgresql.org/about/newsarchive/) |
| pgvector 0.8.7 (2026-10-01) fixes an IVFFlat-build CVE. 0.9.0 is unreleased (HNSW async I/O, drops PG 13/14). The 0.8.2 and 0.8.3–0.8.4 fixes are as stated. Neon's PG18 ships 0.8.6 | Confirmed | The CVE is CVE-2026-103484, a buffer overflow that can allow arbitrary code execution; it was announced 2026-10-05. Neon's 0.8.6 lacks the fix, which supports self-hosting with a ≥0.8.7 pin | [CHANGELOG](https://github.com/pgvector/pgvector/blob/master/CHANGELOG.md), [0.8.7 announcement](https://www.postgresql.org/about/news/pgvector-087-released-3392/), [Neon extensions](https://neon.com/docs/extensions/pg-extensions) |
| The PG18 extension stack exists: PostGIS 3.6.x, h3/h3_postgis 4.2.3, and pgmq 1.10 (PostgreSQL License, PG 14–18; visibility timeouts, archive, FIFO groups) | Confirmed | Neon's PG18 lists PostGIS 3.6.4 and h3 4.2.3. pgmq's README states PG 14–18 and ships a v1.10.0 image. Neon doesn't offer pgmq, another point for self-hosting | [Neon extensions](https://neon.com/docs/extensions/pg-extensions), [pgmq](https://github.com/pgmq/pgmq) |
| Prefect is acquiring Dagster Labs (announced 2026-07-13). Dagster keeps its name, OSS license and roadmap. Prefect is "now Dagster's parent" | Partially true | The date and the name and roadmap commitments are confirmed. Neither announcement mentions the license, though dagster 1.13.27 (2026-10-26) is still Apache-2.0. Neither says the deal has closed, so "parent" is premature | [Dagster letter](https://dagster.io/blog/prefect-is-acquiring-dagster), [Prefect letter](https://www.prefect.io/prefect-acquires-dagster), [PyPI dagster](https://pypi.org/project/dagster/) |
| Dagster+ Solo costs $10/mo + $0.040/credit, with 1 credit per asset materialization or op, so 15-min partitions cost ≈$576/mo | Confirmed | 96 × 5 × 30 = 14,400 credits × $0.04 = $576, plus the $10 base. Serverless compute adds $0.010/min | [Dagster pricing](https://dagster.io/pricing) |
| Neon deprecated pg_search on 2026-03-19 and retired it on 2026-09-21 | Confirmed | Neon now points BM25 users to its own Lakebase text search | [Neon pg_search](https://neon.com/docs/extensions/pg_search) |
| TimescaleDB hypercore and continuous aggregates are TSL-only, and Supabase dropped TimescaleDB on PG17 | Confirmed | Supabase announced on 2025-05-22 that the PG17 bundle drops timescaledb. Tiger Data's editions page marks columnstore/hypercore and continuous aggregates as Community (TSL) only. Neon ships only the Apache-2 subset | [Timescale editions](https://www.tigerdata.com/docs/about/latest/timescaledb-editions), [Supabase PG17 notes](https://supabase.com/changelog/35851-forthcoming-postgres-17-release-notes) |
| Kuzu was archived in Oct 2025 (last release 0.11.x; Kineviz "bighorn" fork). Bytewax is abandoned, with no release since v0.21.1 (Nov 2024) | Partially true | Kuzu is confirmed (last release 0.11.0, July 2025); the Apple-acquisition reports remain unverified. Bytewax the company folded and nothing has shipped after v0.21.1, but a community-maintained restart has been under way since May 2026 (v0.22.0rc1 planned) | [The Register](https://www.theregister.com/2025/10/14/kuzudb_abandoned/), [Bytewax #560](https://github.com/bytewax/bytewax/issues/560), [Bytewax releases](https://github.com/bytewax/bytewax/releases) |
| Hetzner after 2026-06-15, ex-VAT: CPX32 €35.49, CPX42 €69.49, CCX13 €42.99; Cost-Optimized CX/CAX can't be ordered | Confirmed | These are Germany/Finland prices without the primary IPv4; with it they are €35.99 / €69.99 / €43.49. US sites cost far more (CPX31, 4 vCPU / 8 GB, is €62.99). Hetzner's cloud page marks Cost-Optimized "currently not available" | [Price adjustment](https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/), [Regular Performance](https://www.hetzner.com/cloud/regular-performance), [General Purpose](https://www.hetzner.com/cloud/general-purpose), [Hetzner Cloud](https://www.hetzner.com/cloud/) |
| Hetzner raised cloud prices 30–37% in April 2026 and CPX/CCX 113–176% in June 2026, citing hardware costs | Partially true | Hetzner documents only the 15 June 2026 adjustment, which it attributes to higher procurement prices. That one change raised CX/CAX by ≈31–38% and CPX/CCX by ≈144–173% on the Germany/Finland plans checked. No April 2026 change appears on Hetzner's pages | [Price adjustment](https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/), [Price-adjustment FAQ](https://docs.hetzner.com/general/infrastructure-and-availability/faq-standardization-and-price-adjustment/) |
| R2 costs $0.015/GB-month with 10 GB free and $0 egress. DuckDB 1.5 (2026-03-09) adds a core GEOMETRY type. DuckLake 1.0 (2026-04-13) offers PG/SQLite/DuckDB catalogs, inlining, Iceberg-compatible bucket partitioning and DataFusion/Spark/Trino readers | Confirmed | R2's free tier also includes 1M Class A and 10M Class B operations. Most geometry functions still live in DuckDB's spatial extension. DuckLake inlining is on by default (10-row threshold), and DuckLake 1.0 ships with DuckDB 1.5.2 | [R2 pricing](https://developers.cloudflare.com/r2/pricing/), [DuckDB 1.5](https://duckdb.org/2026/03/09/announcing-duckdb-150), [DuckLake 1.0](https://ducklake.select/2026/04/13/ducklake-10/) |
| Qdrant 1.20 (2026-10-22) ranks BM25 directly on stored text. The free cluster has 1 GB RAM / 4 GB disk and suspends after a week idle | Confirmed | The feature is BM25 scoring on the full-text payload index. The free cluster has 0.5 vCPU and is deleted after 4 weeks suspended. Upgrade the [M] tag to [H] | [Qdrant releases](https://github.com/qdrant/qdrant/releases), [Qdrant Cloud](https://qdrant.tech/cloud/) |
| FastAPI 0.162.0 (2026-10-23) has SSE (`EventSourceResponse`), JSON Lines and OpenTelemetry docs. NATS stays in CNCF under Apache-2.0, with its trademarks going to the Linux Foundation. Kafka 4.2 share groups are production-ready (Feb 2026) | Confirmed | FastAPI 0.162.0 has one breaking change: omitted boolean form fields no longer default to `False` | [FastAPI release notes](https://fastapi.tiangolo.com/release-notes/), [FastAPI 0.162.0](https://github.com/fastapi/fastapi/releases/tag/0.162.0), [CNCF on NATS](https://www.cncf.io/blog/2025/05/01/protecting-nats-and-the-integrity-of-open-source-cncfs-commitment-to-the-community), [The Register on NATS](https://www.theregister.com/2025/05/02/cncf_synadia_nats/), [Kafka 4.2](https://www.confluent.io/blog/apache-kafka-4-2-release/) |

**Net effect on the plan:** nothing here changes the architecture. Three planning inputs move:
1. Hetzner prices hold only for an EU VM (add €0.50/mo for IPv4); budget again if the VM must be in the US.
2. The Prefect–Dagster ADR should treat the deal as pending, with no written license commitment.
3. pgvector ≥0.8.7 is now a security requirement, which rules out Neon's 0.8.6 for vectors.
