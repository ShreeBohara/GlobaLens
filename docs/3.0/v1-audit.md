# GlobaLens v1 — Current-State Audit (written after reading every file in the repo)

Repo: `/Users/shree/Desktop/GlobaLens` · ~1,730 lines total · 13 commits (June 11–14 2025 hackathon, then a few
"GCP" deploy commits; messages like "FInal", "Push"). Product pitch in README: "AI-powered platform that turns the
fire-hose of global news into an interactive, searchable world map … GDELT, geospatial visualization, semantic
vector search … for journalists, analysts, and decision-makers."

## The README describes a system that mostly does not exist
README claims Cloud Scheduler + Cloud Functions ingestion, Vertex AI summaries/sentiment, Docker Compose, GitHub
Actions, Terraform (`infra/`), Zustand, Pydantic, Atlas Triggers, event-type filters, timelines, a "Find similar"
button, alerting. **None of these are in the repo.** No tests, no CI, no Dockerfiles, no IaC, no `.env.example`,
no LICENSE file, no typed API contract, no observability, no auth.

## What actually exists

### Frontend — `Frontend/globe/` (Vite 6 + React 19 + react-globe.gl/three.js + Tailwind v4 + framer-motion), ~700 LOC
- Single page. Full-screen `react-globe.gl` globe (blue-marble texture from unpkg), all points one color
  (`#32ff7e`), `pointsMerge` for perf, no clustering, no categories, no time animation.
- **Signature idea — "the Lens":** a fixed circular reticle at screen center (`CircleSelector`, sonar-ring animation
  while dragging). You rotate the planet *under* the lens; points whose screen projection falls inside the circle
  (front-facing only) are listed in a left "News in View" panel (top 10). This is the one genuinely distinctive UX
  concept in v1 and is worth evolving into the product's signature interaction.
- Right column: "ChatPanel" (titled "Semantic Search") — not a chat/LLM; it sends the text to `/api/vector_search`
  and echoes a status string. Below it a date-range filter (`Sidebar`).
- `NewsModal`: title, date, summary, "Read full article" link. Calls hooks after an early `return` (Rules of Hooks
  violation).
- Hardcoded `API_ROOT = 'http://127.0.0.1:5001'` (so the Firebase `/api/**` rewrite is never used in prod).
- Fetches up to 2,000 docs in one JSON payload; client filters/renders everything.
- Tooling issues: `.tsx` files but no `tsconfig`; ESLint config only covers `js/jsx`; `main.jsx` imports `./App.jsx`
  while the file is `App.tsx`; Tailwind v4 with a v3-style `tailwind.config.cjs` inside `src/` (ignored) so custom
  classes (`bg-midnight`, `text-neon`, `animate-fadeIn`, `text-glow-neon`) don't exist; unused deps (bootstrap,
  axios, lodash, react-date-picker, tiles-provider); `index.html` title is "Vite + React"; `sampleNews.ts` doesn't
  match the `NewsPoint` type.

### Backend — `backend/data_fetch/app.py` (Flask, 169 LOC)
- `GET /api/news?q&from&to&limit` → MongoDB Atlas `$search` (text, wildcard path) + `$match` on lat/lng not null and
  `SQLDATE` string range; `$limit` ≤ 2,000.
- `GET /api/vector_search?q&limit` → embeds query with **SBERT `all-mpnet-base-v2`** (English-only, 768-d), loaded at
  import; Atlas `$vectorSearch` on `summary_embedding`, `numCandidates` 2,000, fixed score threshold 0.7.
- DB `news_database`, collection hardcoded **`temp`**. CORS `*`. No auth, rate limiting, pagination, caching,
  validation, logging/metrics, or tests. Port 5001. Deployed (per firebase.json) as Cloud Run `globalens-backend`.

### Pipeline — `process-articles/process_articles.py` (389 LOC), run manually on a laptop
- Loop: find oldest `cleaned_data/*_cleaned.csv` in a GCS bucket (the GDELT export → "clean" step that produces
  these CSVs is **not in the repo**), download, read `SOURCEURL`s, fetch HTML with aiohttp (10 concurrent, spoofed
  Chrome UA), parse with **newspaper3k** in a process pool (title/text + newspaper's *extractive* summary/keywords —
  not an LLM), embed the summary with SBERT, `insert_many` into Mongo **`articles`** (no upsert/dedupe/idempotency),
  move CSV to `backup_data/`.
- Bugs/risks: writes to `articles` while the API reads `temp`; `local_ndjson_output_path` can be referenced in
  `finally` before assignment; full article text stored (copyright exposure); no retries/backoff/robots.txt.

### `populateDB/populate_db.py` (74 LOC)
- **Drops `temp` and inserts 300,000 Faker documents** with random coordinates and random 768-d "embeddings".
  Since the API reads `temp`, the demo very likely showed synthetic data, and semantic search over random vectors
  is meaningless.

## What's worth keeping
- Name + tagline ("GlobaLens: See Beyond the Headlines"), the core idea (world news → geospatial → semantic/AI),
  GDELT as backbone, the dark cosmic aesthetic, and above all **the Lens interaction** (rotate the world under a
  reticle to reveal what's happening there) — to be reimagined as the signature feature.

## Bottom line
v1 is a ~1.7k-LOC hackathon prototype: one Flask file, one manual script, a fake-data seeder, and a single-page
globe. Essentially everything should be rebuilt; the *concept* is the asset.
