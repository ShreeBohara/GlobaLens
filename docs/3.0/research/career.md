# GlobaLens 3.0: Career-Signal Research

*What makes a portfolio project get an early-career SWE / ML / AI / data engineer hired in 2025-2026, and what that means for GlobaLens 3.0.*

Date: 2026-10-28. Confidence tags: **[H]** = primary or strong source checked this session · **[M]** = secondary or single source · **[L]** = opinion or weak source · *(mem)* = from prior knowledge, not re-checked this session. Method note: the shared web-search budget ran out partway through. After that I only fetched primary pages I already knew the URLs for. Claims I could not re-check are tagged *(mem)*.

---

## TL;DR

1. **The resume screen is fast, noisy and driven by brand names.** It takes about 30 seconds. A project helps there only if one line carries a **checkable number that works like a brand**: real users, a known launch, or a published benchmark. Depth pays off later, in interviews.
2. **Proof beats polish.** The signals that are hardest to fake are a live demo with no signup, real usage, reproducible benchmarks and evals, and written trade-offs. Stars, lines of code and tool lists count for little.
3. **Companies expect you to build with AI, and they penalize code you don't own.** Companies now openly test judgment about AI output and expect "full ownership." GlobaLens needs *verification artifacts* (tests, evals, ADRs, benchmarks), and Shree must be able to explain every part without AI help.
4. **v1's README describes a system that mostly doesn't exist.** It lists Vertex AI, Cloud Functions, Scheduler, Docker Compose, GitHub Actions, Zustand and Pydantic, and none of them are in the repo. This is the single worst red flag to fix. 3.0 needs a **claims ledger** and a **public live-metrics page**.
5. **Product direction warning:** **World Monitor** already owns "AI world-news dashboard on a globe." It launched January 2026 as a weekend project, claims 2M+ users, has about 89.7k GitHub stars, uses the same globe.gl + Three.js stack, carries 468 feeds and AI briefs, runs an MCP server, and sells a $39.99/mo Pro tier. GlobaLens cannot win on breadth. It needs a **depth and provenance wedge** built around the Lens.
6. **Target T-shape:** go deep on (a) a real-time geo-news data pipeline and (b) AI retrieval and evals. Use frontend polish as the hook. Keep infrastructure boring and cheap.

---

## 1. Context: why the bar is higher in 2026

- Employment of 22-25-year-old software developers was about **20% below its late-2022 peak** by July 2025. The Stanford/ADP authors estimate a **16% relative decline** for early-career workers in AI-exposed jobs. **[H]**
- At big tech, new-grad hiring is down **~50% vs. pre-pandemic**, and new grads make up **~7% of hires** (SignalFire 2025). **[M]**
- **Resume screens are noisy and favor pedigree.** In the interviewing.io + Learning Collider replication (76 recruiters, ~2,200 evaluations of 1,000+ resumes), recruiters picked correctly **55%** of the time, the **median review took 31 s**, and two recruiters agreed only **64%** of the time. FAANG-tier experience made a candidate **35% more likely** to be picked. Engineering hiring managers scored **48%**. **[H for the numbers; caveat: the vendor ran the study on its own users]**

**Implication:** Shree has no FAANG brand, so the project has to work as the brand. One resume line must state something a stranger can check in seconds, such as "2,400 weekly users", "Show HN front page" or "open benchmark cited by X." The 30-minute deep dive comes later.

---

## 2. Which signals matter, ranked for GlobaLens

| # | Signal | Evidence | GlobaLens requirement |
|---|---|---|---|
| 1 | **Live demo, no signup, real data** | Show HN wants things people can try, and says to avoid signups. **[H]** StartDataEngineering: "show not tell", with a live dashboard on near-real-time data linked from the resume. **[M]** | Public URL from Phase 1. Lens views can be deep-linked. Production never runs on synthetic data. |
| 2 | **Real users and usage** | Hardest to fake. Stars are a weak signal: about 6M suspected fake stars were found (ICSE'26 paper). **[H]** Anthropic: "We care about what you can do, not where you learned to do it." **[H]** | Public `/stats` page showing weekly active users, returning users, API keys and embeds. |
| 3 | **Measured performance** | METR RCT: developers believed AI made them ~20% faster, but they were measured **19% slower**. Perception is not measurement. **[H]** | Reproducible load tests, Core Web Vitals at p75, FPS, data freshness, monthly cost. |
| 4 | **Evals for AI features** | Hamel Husain: failed AI products share "a failure to create robust evaluation systems." **[H]** | Hand-labeled eval set, with CI gated on eval scores. |
| 5 | **Written thinking** | Anthropic tells candidates to put "interesting independent research, … a thoughtful blog post, or … open source" at the top of the resume. **[H]** Google-style design docs focus on trade-offs (Ubl). **[H]** ADRs (Nygard). **[H]** | One design doc per phase, ADRs, and 3-4 case-study posts. |
| 6 | **Engineering hygiene** | StartDataEngineering lists tests, linting, type checks and scheduled runs. **[M]** These are table stakes: missing them hurts more than having them helps. | CI on every PR, a typed API contract, and infrastructure-as-code that deploys the real system. |
| 7 | **Design quality** | Decides the first 10 seconds. Core Web Vitals give objective bars: LCP ≤2.5 s, INP ≤200 ms, CLS ≤0.1, all at p75. **[H]** | The Lens runs at 60 fps and meets those Core Web Vitals. |
| 8 | **OSS adoption** | Stars alone are weak (see #2). Dependents and downloads of a reusable package are stronger. **[M]** | Extract one package, such as the Lens component or the GDELT client. |
| 9 | **Demo video** | For reviewers who never click the link. **[L]** | 90-second captioned video. |
| 10 | **Distribution** | Paul Graham: the most common unscalable thing founders do early is recruit users by hand, from a narrow group. **[H]** | Win a niche first, then post a Show HN. |

---

## 3. Red flags (and v1's record)

| Red flag | Evidence | v1 | Rule for 3.0 |
|---|---|---|---|
| **README describes a system that doesn't exist** | Anthropic forbids inventing experiences in applications. **[H]** Canva expects engineers to "take full ownership of any code they produce." **[H]** Interviews dig into whatever you claim. | **Yes.** It claims Vertex AI, Scheduler, Cloud Functions, Docker Compose, GitHub Actions, Zustand, Pydantic, "Find similar" and timelines, and says React 18 when the repo uses React 19. | Keep a claims ledger: every README claim links to code, a CI run or a metric. Add a status table (Implemented / In progress / Planned). Tag v1 honestly. |
| **Synthetic data shown as real** | Credibility collapses once someone notices. | **Yes.** 300k Faker docs with random 768-d "embeddings". | The demo shows real data only. Synthetic data is allowed only in load tests, clearly labeled. |
| **Tutorial clone or thin AI wrapper** | Career-content consensus is that PDF chatbots and LangChain demos get dismissed unread. **[L]** | Partly. The "chat" panel was really just search. | Every AI feature has an eval and does something a wrapper can't. |
| **Buzzword soup / résumé-driven development** | ICSE-SEIS 2021 survey of 591 professionals: **82%** of technical staff believe trendy tech makes them more attractive, and **60%** of hiring professionals say trends shape their job ads. The paper treats the resulting overemphasis on hype as a dysfunction. **[H]** | **Yes.** The README tool list. | Every component needs an ADR giving a measured reason. |
| **Microservices or Kubernetes with no load to justify them** | Prime Video moved a monitoring service to a monolith and cut its cost ~90% (2023). *(mem)* | n/a | A modular monolith plus one worker. Kubernetes, C++ or extra services only with an ADR and a benchmark. |
| **Agent soup** | Anthropic: "finding the simplest solution possible, and only increasing complexity when needed." It also warns that frameworks hide prompts and make debugging harder. **[H]** | n/a | Start with fixed workflows. Use agents only where evals show a gain. |
| **Broken demo** | A demo that returns 500 errors is worse than no demo. **[L]** | API hardcoded to `127.0.0.1` in production. | Uptime checks, a cached snapshot that loads when the API is down, and budget alerts. |
| **Sloppy history** | Reviewers skim commits. **[L]** | Commit messages like "FInal" and "Push". | Small PRs with rationale, conventional commits, a tagged release per phase. |
| **Bought stars** | Fake stars give a boost for less than ~2 months, then become a liability. **[H]** | No | Never buy stars. |
| **Copyright and scraping risk** | Shows weak judgment. **[L]** | Stores full article text and spoofs the user agent. | Store metadata, short snippets and links. Respect robots.txt. |
| **Lines of code as a goal** | AI makes code cheap, and reviewers know it. A huge solo codebase raises questions about maintainability and who reviewed it. **[L, opinion]** | n/a | Report capabilities and outcomes. Never put LOC on the resume. |

---

## 4. AI-assisted projects in 2026: how they're judged and how to show ownership

**Using AI is now expected:**
- Shopify's April 2025 memo: "Reflexive AI usage is now a baseline expectation." **[M]**
- Canva (June 11, 2025) **expects** backend, ML and frontend candidates to use Copilot, Cursor or Claude in interviews. For backend and frontend it **replaced the CS-fundamentals screen** with an AI-assisted coding round. **[H]**
- Meta piloted AI-assisted coding interviews, reported in July 2025 by 404 Media and confirmed by Meta as a test. **[M]**

**What gets assessed:** Canva asks "Can they identify and fix issues in AI-generated code?" and expects full ownership of every line. Candidates with little AI experience struggled for lack of *judgment*, not coding skill. **[H]**

**The limits:** Anthropic says to "create your first draft yourself, then use Claude to refine it." Take-homes and live interviews are done without AI unless they say otherwise, and candidates should be open about their AI use. **[H]** So Shree must be able to **whiteboard GlobaLens without AI help**.

**Developers remain skeptical:**
- Stack Overflow 2025: 84% use or plan to use AI, but 46% distrust its accuracy versus 33% who trust it. 66% name "almost right, but not quite" as a frustration. 72% say they don't vibe code at work, and only about 31% use agents at work. **[H]**
- Addy Osmani's "70% problem": AI drafts quickly, but the last 30% (edge cases, security, integration) needs engineering judgment. **[H]**

**Interpretation:** "Built with Claude Code" is neutral to positive. "Can't explain it" is fatal. A large volume of AI-generated code impresses nobody. Behavior you have verified does.

**Ownership protocol (requirements for the plan):**
1. **Human-first docs.** Shree writes the first draft of each design doc and ADR, and AI acts as critic. This mirrors Anthropic's rule.
2. **Disclosure.** Add `docs/ai-workflow.md` and a README section, "How this was built." It lists the tools, the gates code must pass (tests, evals, review) and what was written by hand.
3. **2-3 hand-built "depth kernels," each with a blog post:** the Lens's screen-space selection and clustering, near-duplicate story clustering (MinHash/SimHash), and geocoding and entity disambiguation.
4. **Same bar for all code.** AI-written code must pass the same evals and benchmarks in CI as hand-written code.
5. **Explain-back.** After each phase, record a 10-minute architecture walkthrough with no notes or AI. Keep a "what I'd change" log.
6. **Real postmortems** for real incidents, such as a cost spike or a stalled ingestion run. These are strong evidence of ownership.

---

## 5. Project shapes by role, mapped to GlobaLens

| Role | What impresses | GlobaLens slice | Headline metrics |
|---|---|---|---|
| **SWE (systems/backend)** | Concurrency, idempotency, failure handling, service-level objectives, load tests, cost awareness | Real-time ingestion plus a space-time Lens query API, with backpressure, retries and idempotent upserts | p95/p99 latency at N requests/s (k6); freshness p95; error budget |
| **Data engineer** | Live dashboard on near-real-time data, architecture diagram, tests, scheduled runs, data-quality checks (StartDataEngineering) **[M]** | GDELT, updated every 15 minutes *(mem)*, flowing through raw → cleaned → curated layers, with dedupe, geocoding, data-quality tests, backfills and lineage | Events/day; freshness p50/p95; dedupe ratio; % geocoded; data-quality pass rate; $ per 1M events |
| **ML engineer** | A model, a baseline, a held-out eval and error analysis | Multilingual event geolocation, story clustering, embedding retrieval | Median geolocation error (km), accuracy at country level, clustering V-measure, recall@10 / nDCG |
| **AI engineer** | RAG or agents with evals, citations, tracing and cost/latency trade-offs, simplest design first (Anthropic) **[H]** | "Ask the Lens" (grounded Q&A) and daily briefs, both with citations; analysis of how coverage differs across countries | Citation precision, faithfulness, retrieval recall, $/query, p95 latency |
| **Frontend / design engineer** | Performance, polish, accessibility | The Lens: a 3D globe with 100k+ points at 60 fps, time scrubbing, keyboard and reduced-motion support | Core Web Vitals at p75, FPS at N points, JS KB, accessibility audit |

**Call:** go deep on the data pipeline and on AI evals. The frontend is the signature hook. Infrastructure stays boring.

---

## 6. Presenting the project

**Resume bullets.**
- Use Bock's formula: "Accomplished [X] as measured by [Y], by doing [Z]." **[M]**
- Frame value, not tools. Patrick McKenzie: "Engineers are hired to create business value, not to program things." **[H]**
- One page. Link each project. **[H]**

Bullet templates. Fill them **only with measured numbers taken from the metrics ledger**:
- "Built a real-time geo-news pipeline processing **N events/day** from GDELT with idempotent upserts. Held p95 freshness at **M min** and **99.x%** run success over 30 days."
- "Raised article geolocation accuracy at country level from **A% to B%** (median error **C to D km**) on a **1,000-item** hand-labeled multilingual eval set by adding entity linking and gazetteer disambiguation."
- "Cut Lens interaction latency (INP at p75) from **X to Y ms** at **Z k** points by moving selection to a Web Worker and using GPU instancing."
- "Launched on Show HN (**P** points). Grew to **U** weekly users in **K** countries, plus **E** external embeds and API keys."
- Keep three resume variants: SWE, AI/ML and data. Each gets 3 bullets, a live URL and the repo link.

**README order:** (1) one-sentence pitch and a hero GIF of the Lens; (2) a **Try it** link with no signup; (3) key numbers, each linked to `/stats`; (4) a **What's real** status table; (5) C4 context and container diagrams in Mermaid, which GitHub renders *(mem)*; (6) **evals and benchmarks** with reproduce commands; (7) **"How is this different from World Monitor / GDELT / Ground News?"**; (8) ADR index and design docs; (9) a one-command quickstart; (10) **How this was built**, including the AI disclosure; (11) limitations and roadmap; (12) data attributions and license.

**Video:** 90 seconds, captioned. Show the problem, then the Lens, then a story timeline, then a cited brief, then the under-the-hood metrics.

**Writing:** one case study every ~2 phases. Topics: how the Lens renders 100k points, building a geo-news eval set, running a real-time global map for ≤$50/mo, and a postmortem. This matches Anthropic's resume advice and swyx's "learn in public." **[H]**

**Launch:**
- Recruit the first 20-50 users by hand from one narrow group (Paul Graham). **[H]**
- Then post a Show HN, once the no-signup demo is solid. Stay in the thread to answer questions and never ask for votes. **[H]**
- Product Hunt is optional. I couldn't check how well it works in 2026. **[L]**
- Give a lightning talk at a local meetup.

---

## 7. Famous side projects and what made them work

| Project | What happened | Lesson for GlobaLens |
|---|---|---|
| **World Monitor** | Started January 2026 as a weekend project. Reached "hundreds of thousands" of users in week 1 and claims 2M+ users now. About 89.7k stars and 13.8k forks. Its builder is the CEO of Anghami. **[H, user counts self-reported]** | Timing, breadth and "no account" work. It is also GlobaLens's incumbent, so differentiate. |
| **Flightradar24** | Founded 2006 by two Swedish aviation enthusiasts. Now 4M+ users a day and 40k+ crowdsourced receivers. **[M]** | A live map of the world can be the whole product. A contributor network is the moat. |
| **Bun** | Grew out of Jarred Sumner's frustration with slow test runs while building a voxel game. Anthropic acquired it on Dec 2, 2025. **[H]** | Pick a measurable edge (speed) on a problem you feel yourself. |
| **Chris Olah / Distill** | No degree. A Distill paper led to his OpenAI job, and he later co-founded Anthropic. **[M]** | Clear, visual technical writing is a hiring signal. |
| **Homebrew** | Written by Max Howell (2009). **[H]** His widely reported 2015 tweet about Google rejecting him over a binary-tree question *(mem)*. | Adoption gets you noticed, but you still have to pass interviews. |
| **LangChain, LlamaIndex, Excalidraw, Gmail** | All began as side projects and became companies or products. *(mem)* | One signature idea, shipped in public, iterated fast. |

**What they share:** they solve the builder's own problem, anyone can try them instantly, each has one signature interaction, each has a measurable edge, they kept shipping, and several rode a news moment.

---

## 8. Implication for what GlobaLens should *be*

- **Don't build "World Monitor but mine."** World Monitor already does breadth very well (468 feeds, 59 layer types, globe plus flat map, MCP server, SDKs, desktop app). A reviewer who knows the space will call a breadth-play a clone.
- **Positioning:** *World Monitor shows what is happening everywhere right now. GlobaLens shows how a story unfolds, who covers it, how the framing differs across countries and languages, and what is being missed.* That is "See beyond the headlines," taken literally.
- **Signature:** the **Lens as an instrument across space, time and topic**. You can scrub history, compare coverage inside the reticle, and find under-covered events.
- **A trust layer as part of the product:** every AI output carries citations and is scored on public eval dashboards.
- **A niche with a weekly need, so it gets real users.** Candidates: Model UN and debate students and teachers, journalism students, OSINT hobbyists. **[L]** Validate with 5-10 user conversations.
- **Reasons to come back:** watchlists, a weekly digest, and shareable Lens permalinks and embeds with social preview images. Keep only view state in URLs, never personal data.

---

## Recommendations for GlobaLens 3.0

1. **MUST: build honesty in from day one.** Keep a claims ledger, with a README status table generated from CI and deploy state. Run a public live `/stats` page so every resume number can be checked. Tag v1 `v1-hackathon` and write a short, honest retrospective; the before-and-after story is an asset.
2. **MUST: a live, no-signup demo by the end of Phase 1-2, kept alive.** It needs uptime monitoring, a cached snapshot for when the API is down, cost alerts, and real data only.
3. **MUST: differentiate from World Monitor in the product itself.** Use the depth and provenance wedge (story evolution, coverage divergence, citations scored by evals) around the Lens. Answer "How is this different?" in the README.
4. **MUST: an eval harness and a hand-labeled dataset by the middle phases.**
   - At least 500-1,000 multilingual items, with a second annotator labeling part of them to measure inter-annotator agreement.
   - Gate CI on eval scores.
   - Publish the dataset as an open benchmark, which also creates an artifact others can adopt.
5. **MUST: publish the metrics table below and track it per release.** Resume bullets come only from these measured numbers.
6. **MUST: follow the AI ownership protocol (§4).** Human-first docs, disclosure, 2-3 hand-built depth kernels, explain-back recordings, and the ability to whiteboard the system without AI help.
7. **SHOULD: no résumé-driven development.** Start with a modular monolith and one worker. Terraform is fine because it deploys the real infrastructure. Kubernetes, microservices and C++ only with an ADR and a benchmark showing the need.
8. **SHOULD: produce the docs artifacts every phase.** A design doc (Ubl's sections), ADRs (Nygard), C4 diagrams, a changelog, and postmortems for real incidents.
9. **SHOULD: get users before the launch.** Hand-recruit one niche, then post a Show HN once the gates below pass, then write a case study.
10. **COULD: extract one reusable OSS package** (Lens component, GDELT client, or dedupe library) to earn real dependents.
11. **COULD:** give a meetup talk, publish a benchmark write-up comparing models on geo-news tasks (cost vs. accuracy), and record the 90-second video.

**What every phase must ship:**

| Every phase | Every 2-3 phases | Before Show HN (launch gate) |
|---|---|---|
| Tagged release and changelog. Live demo updated. GIF. Change in metrics on `/stats`. At least 1 ADR. CI and evals green. Private 10-minute explain-back recording. | Case-study blog post. Updated architecture diagram. Resume bullets refreshed from the metrics ledger. | No signup needed to try it. p95 latency on target at 10× expected load. Cached fallback works. Cost cap set. Privacy-friendly analytics and error tracking. Feedback channel. 20+ real niche users. |

**Metrics to measure and publish** (proposed targets in brackets are initial opinions):

| Area | Metrics |
|---|---|
| Product | Weekly active users, returning users at 7 and 30 days, countries reached, shares and embeds, feedback items [100 weekly users from the niche before Show HN] |
| Pipeline | Events/day; freshness p50/p95 from GDELT publish to visible on the globe [p95 < 30 min]; run success %; dedupe ratio; % geocoded; data-quality pass rate |
| API | p50/p95/p99 latency at a stated request rate (k6); error rate; cache hit rate |
| Frontend | LCP/INP/CLS at p75 [≤2.5 s / ≤200 ms / ≤0.1]; FPS at N points on a mid-range laptop and phone; JS KB; accessibility score |
| AI / ML | Geolocation accuracy and median km error; retrieval recall@k and nDCG; citation precision; faithfulness; $ per brief; p95 generation time; eval-set size and inter-annotator agreement (κ) |
| Ops / cost | Uptime %, time to recover, $/month [≤$50], $ per 1k requests, number of postmortems |

---

## Sources

- interviewing.io + Learning Collider, recruiter resume study: https://interviewing.io/blog/are-recruiters-better-than-a-coin-flip-at-judging-resumes
- Anthropic careers page: https://www.anthropic.com/careers
- Anthropic candidate AI guidance: https://www.anthropic.com/candidate-ai-guidance
- Canva, "Yes, you can use AI in our interviews" (June 11, 2025): https://canva.dev/blog/engineering/yes-you-can-use-ai-in-our-interviews
- Meta AI-assisted interview pilot (secondary; original by 404 Media): https://www.hrgrapevine.com/us/content/article/2025-08-01-meta-trialling-ai-assisted-interview-process-for-new-coding-hires
- Shopify "reflexive AI" memo coverage: https://www.digitalcommerce360.com/2025/04/08/internal-memo-shopify-ceo-declares-ai-non-optional/
- Stack Overflow Developer Survey 2025, AI section: https://survey.stackoverflow.co/2025/ai
- METR RCT (July 10, 2025): https://metr.org/blog/2025-07-10-early-2025-ai-experienced-os-dev-study/
- Addy Osmani, "The 70% Problem": https://addyosmani.com/agentic-engineering/the-70-percent-problem/
- Hamel Husain, "Your AI Product Needs Evals" (Mar 2024): https://hamel.dev/blog/posts/evals/
- Anthropic, "Building effective agents" (Dec 19, 2024): https://www.anthropic.com/engineering/building-effective-agents
- Fritzsch et al., "Résumé-Driven Development" (ICSE-SEIS 2021): https://arxiv.org/abs/2101.12703
- He et al., "Six Million (Suspected) Fake Stars in GitHub" (ICSE'26): https://arxiv.org/abs/2412.13459
- World Monitor repo: https://github.com/koala73/worldmonitor
- World Monitor about page: https://www.worldmonitor.app/docs/about
- Show HN guidelines: https://news.ycombinator.com/showhn.html
- Paul Graham, "Do Things That Don't Scale": https://paulgraham.com/ds.html
- Malte Ubl, "Design Docs at Google": https://www.industrialempathy.com/posts/design-docs-at-google/
- Michael Nygard, "Documenting Architecture Decisions": https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions
- StartDataEngineering (Joseph Machado), designing a project to impress hiring managers: https://www.startdataengineering.com/post/data-engineering-project-to-impress-hiring-managers/
- StartDataEngineering, choosing a portfolio project: https://www.startdataengineering.com/post/what-data-project-to-build/
- web.dev, Core Web Vitals: https://web.dev/articles/vitals
- SignalFire, State of Tech Talent 2025: https://www.signalfire.com/blog/signalfire-state-of-talent-report-2025
- Stanford Digital Economy Lab follow-up (Feb 2026): https://digitaleconomy.stanford.edu/news/canaries-interest-rates-and-timinga-more-on-recent-drivers-of-employment-changes-for-young-workers
- ADP Research summary: https://www.adpresearch.com/yes-ai-is-affecting-employment-heres-the-data
- XYZ formula (Inc. coverage of Laszlo Bock): https://www.inc.com/bill-murphy-jr/google-recruiters-say-these-5-resume-tips-including-x-y-z-formula-will-improve-your-odds-of-getting-hired-at-google.html
- Patrick McKenzie, "Don't Call Yourself A Programmer": https://www.kalzumeus.com/2011/10/28/dont-call-yourself-a-programmer/
- Tech Interview Handbook, resume guide: https://www.techinterviewhandbook.org/resume/
- swyx, "Learn In Public": https://www.swyx.io/learn-in-public
- Bun joins Anthropic (Dec 2, 2025): https://bun.com/blog/bun-joins-anthropic
- Flightradar24 (Wikipedia): https://en.wikipedia.org/wiki/Flightradar24
- Chris Olah (Wikipedia): https://en.wikipedia.org/wiki/Chris_Olah
- Homebrew (Wikipedia): https://en.wikipedia.org/wiki/Homebrew_(package_manager)
- Weak career content on AI-wrapper portfolios [L]:
  - https://medium.com/write-a-catalyst/the-ai-portfolio-projects-that-instantly-tells-recruiters-youre-a-junior-f9629b9a38da
  - https://www.dice.com/career-advice/essential-steps-for-turning-side-projects-into-job-offers
- Not re-checked this session *(mem)*: Prime Video's 2023 move to a monolith; GDELT's 15-minute update cadence; GitHub rendering Mermaid; the C4 model (c4model.com); the Max Howell tweet; the origins of LangChain, LlamaIndex, Excalidraw and Gmail.
