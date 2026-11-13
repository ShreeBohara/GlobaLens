# Lead direction: final calls on top of the North Star (2026-10-29)

Where these notes conflict with [`north-star.md`](north-star.md), these notes win. Everything not mentioned here stands as written.

Judge totals were Underexposed (contrarian) 157, Living Planet (experience) 141, Atlas (ai-native) 126, Seismograph (systems) 122 and Desk (intelligence) 116. The North Star synthesis (Underexposed thesis + Seismograph engine + Living Planet face + Desk as-of + Atlas evals) is adopted as the product and architecture of record.

## 1. Adopt the North Star, with three framing changes

1. **The product has two layers.** It must not be a single thesis.
   - **(a) The daily driver.** The best way to *explore the world's news by place, language and time*: Viewfinder, the Lens, real headlines, StoryStream and search. This is the v1 idea the user loves, done properly.
   - **(b) The signature.** The only instrument that *measures attention against severity*: Exposure. It makes the product unique and is the launch story.
   - The plan must make (a) excellent and must not starve it to feed (b).
   - **P1:** the Lens lists the actual headlines inside the ring from day one: title (original, plus the English translation where GDELT's translated stream provides it), outlet, language, time and a link out. This is v1's core loop on real data.
   - **P2:** duplicates and syndicated copies collapse into simple "story groups" (URL canonicalization, title hash, MinHash). The list then reads as stories before StoryStream arrives in P4.
2. **Naming.**
   - The product is **GlobaLens**, release 3.0. Drop "Exposure edition".
   - Tagline: **"See beyond the headlines."** The hero line stays as in the North Star.
   - At most five named modes:
     - Lighting modes: **Viewfinder (V)**, **Infrared (I)** and **Exposure (E)**.
     - Tools: **Long Exposure** (time) and **Wavefront** (arcs).
   - The weekly publication is *The Underexposed Report*.
   - Coin no further terms. The judges flagged naming sprawl.
3. **Pivot gate at the end of P3.** If severity fails validation, Exposure becomes a labelled "experimental" mode. Failure means too small a share of listed CARE/ECHO crises can be scored, or external reviewers raise a substantive objection. The plan then continues with Stories, Wavefront and Long Exposure as the signature trio, and must stay strong in that branch. State the gate criteria and the fallback explicitly.

## 2. "Extra, extra crazy": deliver it as depth, craft and evidence, never padding

The two inputs pull in opposite directions:
- **The user** asked for maximal ambition and named C++, systems work, Terraform, infra, AI/ML and CI/CD. They also want 10k → 100k LOC.
- **The research** says plainly that technology adopted before a measured need reads as résumé padding to senior reviewers.

Resolve the tension as follows.

### 2a. The Bake-off Lab (new, cross-cutting)

**Structure:** a `lab/` directory plus `docs/bakeoffs/`.

**Rules for each bake-off:**
- Timeboxed to ≤10 h.
- Answers a decision the plan really faces.
- Pre-registers its metric and adoption threshold before running.
- Uses a reproducible script.
- Publishes an ADR ("considered, measured, chose X") and a short blog post.

The challenger is adopted only if it wins on the pre-registered metric. The user gets hands-on experience with the technology they asked for, and the output is staff-level evidence rather than buzzwords. Total: about six bake-offs, ≤60 h.

| Phase | Bake-off | Decision | Adopt the challenger only if |
|---|---|---|---|
| P1 | Globe renderer spike: MapLibre 6.16 + deck.gl 9.4.1 globe vs a custom-GLSL fallback | Renderer go/no-go | Already in the North Star |
| P2 | Lens kernel: JS typed arrays vs Rust compiled to WASM (wasm-bindgen, SIMD128) | Mobile Lens p95 | WASM is ≥2× faster at p95 on a mid-range Android, or is required to meet 16 ms |
| P4 | Embeddings: harrier-270m vs EmbeddingGemma 2 vs e5-small, with Qwen3-0.6B as the ceiling | Production embedder | Already planned |
| P6 | Decade store: DuckDB on Parquet/cubes vs single-node ClickHouse vs partitioned Postgres, on the ~1B-row attention cube | Replay backend | DuckDB/cubes miss the replay latency SLO |
| P7 | Replay transport: ledger-as-queue vs NATS JetStream vs Redpanda (Kafka API). Replay a month of 15-min files at maximum speed, with exactly-once verified by the chaos harness | Streaming backbone | The ledger is the measured bottleneck |
| P10 | (a) `storystream-core` in Rust/PyO3 vs Python on a full replay (North Star trigger: >12 h replay, ≥99.9% agreement). (b) Compose vs k3s + Argo CD on DR rebuild RTO and upgrade toil | Native kernel; orchestration | It wins on the measurement |

**C++: no.** Nothing in this system needs it. Rust covers native kernels (PyO3, wasm-bindgen) with memory safety and one toolchain. State this once in the decision log so the omission reads as a decision, not an oversight.

### 2b. Make invisible depth visible

The judges' biggest criticism of the systems work was that nobody can see it.
- **`/engine` is a showpiece, not an admin view.** It shows:
  - an animated, live ledger state machine, with files flowing listed → … → published
  - the freshness SLO
  - the last chaos run (kills and hash match)
  - queue depths and a cost meter
  - eval history sparklines

  The pitch is "the backend has a UI too". v1 ships in P2 and the page grows every phase.
- **`/methods/*` interactive explainers** (scrollytelling, d3) cover Exposure (P3/P5), StoryStream (P4) and Wavefront (P7). They double as blog posts and make the method readable for non-experts and interviewers.

### 2c. UI-heavy, done properly

- **The design system is a product:**
  - `packages/ui` holds the tokens and components.
  - A component catalog: pick one of Storybook or Ladle, and say why.
  - Playwright visual regression covers Shots and components.
  - axe runs in CI.
- **"More layers"** means first-class, well-designed **hazard layers** in Infrared: USGS earthquakes, GDACS alerts, FIRMS fire detections, NASA EONET events and UCDP conflict events. They earn their place because they *are* the severity denominator. A day/night terminator and a graticule are cheap additions. No breadth layers (flights, ships, markets).
- **Mobile is a first-class target** with its own performance budget, as in the North Star.

### 2d. AI engineering, earlier and more concrete

- **P5:** a read-only **MCP server** (Streamable HTTP; tools for lens, search, story and exposure) ships as a small item once the API and Crisis Ledgers exist. It is about 300 LOC, cheap and a strong signal.
- **P9:** the MCP App, the bounded Analyst and the agent-eval PR gate stay here.
- Tell the **distillation** story with measured numbers: Haiku adjudications are distilled into the LightGBM linker and new-story classifier, and the result is reported as F1 relative to the LLM, plus dollars saved.

### 2e. Public API and open data

- OpenAPI 3.1 generates the TS client, as planned.
- A small **Python client** for researchers (P8).
- Weekly Parquet open-data drops with a datasheet (P8/P10).

## 3. Topology, cloud and cost: corrected

- **Architecture: unchanged from the North Star.**
  - One stateful VM running Docker Compose behind Cloudflare Tunnel.
  - Cloudflare R2, CDN, Workers and Access.
  - Vercel for Next.js; BigQuery for the backfill.
  - GitHub Actions; OpenTofu.
- **VM size is trigger-gated.**
  - Start on Hetzner **CPX22** (4 GB, €19.99) for P1–P3.
  - Move to **CPX32** (8 GB, €35.99) when the RAM trigger fires: p95 RSS above 80% for 24 h, or sustained swap-in. This most likely happens at P4, when embeddings and StoryStream arrive.
  - Show both monthly budgets: **Lean (~$46)** and **Comfortable (~$62–65)**.
- **GCP variant (documented; the user's choice).**
  - Why offer it: v1 ran on GCP (Cloud Run, Firebase Hosting, GCS) and recent commits added GCP deploy config. GCP is more recognizable on a résumé, and BigQuery is GCP-native.
  - What it is: the VM becomes a Compute Engine e2-medium or e2-standard-2, with WIF from GitHub Actions, Artifact Registry and Secret Manager. The Compose stack and Cloudflare edge are the same; only the OpenTofu compute module differs.
  - Cost: roughly ~$60–85/month.
  - Recommendation: Hetzner, unless the user has GCP credits or wants GCP experience specifically.
  - This is Open Question #1.
- **The ≤$50/month figure is my assumption, not a user requirement.** Present cost honestly per phase and flag it.
- Hard spend caps live in code (the LLM governor), with budget alerts everywhere.

## 4. Corrections to the phase plan

- **Exactly 10 phases, of variable length.** Give effort in hours per phase and the calendar at both 10 h/wk and 20 h/wk, since the user's weekly time is unknown. Each phase should be about 25–50 focused hours.
- **The North Star overloads P1.** Make P1 a minimal walking skeleton:
  - v1 tagged and a retrospective written.
  - Monorepo skeleton.
  - CI (lint, typecheck, tests) and OpenTofu for the VM, R2 and DNS.
  - Poller and ledger for **both** GDELT GKG streams, writing Parquet on R2 plus a last-24h Arrow pack.
  - Next.js globe (MapLibre + deck.gl, precision-sized discs, location honesty).
  - Lens v0: a main-thread JS cap query that lists headlines.
  - The two-clock badge.
  - A deployed public URL.
  - The render-spike ADR in week 1.

  Move the chaos harness, `/engine` v1, attested pull deploys and OTel/Grafana to P2.
- **Hero by P3.** Press E (place-level) must be live by the end of P3. Keep this.
- **Week-0 checklist** before P1, so P3 is never blocked on approvals:
  - Accounts: GitHub org, domain, Cloudflare, Hetzner, Anthropic, a BigQuery project.
  - Data registrations: UCDP token, FIRMS key, ReliefWeb appname.
- **Users and reviewers.** Real users start in P5 (20 from the first niche) and the launch is in P8, as planned. Recruit 2–3 external ethics or humanitarian reviewers during P4–P5.
- **Every phase ends with:** a tagged release, the live demo, a 30–60 s GIF or video, a `/stats` delta, at least one ADR and a short devlog post.

## 5. LOC

LOC is an outcome, not a goal.
- Estimate it honestly per phase and per area: TS web, Python services, SQL, IaC, tests, evals/bench, and Rust if triggered.
- Expect roughly **50–75k total by P10**, including tests and infrastructure.
- Say plainly that "100k" is not a target and that padding would hurt the project.

## 6. Extra content the plan must include

- The **Bake-off Lab** section and the **`/engine` and `/methods`** showpieces.
- **Stop points:** what the user has if they stop after P3, P5 or P8.
- **The pivot gate** after P3: criteria and the fallback branch.
- **Appendix: Week-0 checklist.**
- **Appendix: Execution playbook** for building this with Claude Code:
  - repo conventions (`CLAUDE.md`)
  - the ADR template
  - a per-phase kickoff prompt
  - the definition-of-done checklist
  - the AI-ownership protocol: four hand-written depth kernels, each with an explain-back recording and a blog post

## 7. Open questions to surface, with recommended defaults

1. **Cloud and budget:** Hetzner Lean (~$46), growing to Comfortable (~$62–65) on the RAM trigger (recommended), or the GCP variant (~$60–85), if the user has credits or prioritizes GCP experience.
2. **Weekly hours.** The plan shows calendars for 10 h/wk and 20 h/wk.
3. **The Exposure signature.** Is the user comfortable publishing *The Underexposed Report* under their name, with external reviewers? A fallback branch exists if not.
4. **First niche:** journalism/IR classrooms (recommended) or NGO communications staff.
5. **Logistics:**
   - a GitHub org (needed for the merge queue) and a domain
   - licenses: Apache-2.0 for code, CC BY 4.0 for data
   - v1 tagged `v1-hackathon` and removed from `main`
6. **Annotators:** 1–2 multilingual annotators for the gold sets.
