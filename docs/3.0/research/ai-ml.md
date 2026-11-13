# GlobaLens 3.0 — AI/ML Layer Research (as of 2026-10-28)

**Scope:** embeddings, LLMs & cost, story detection, NER/EL/geoparsing, framing & MT, forecasting, agentic RAG/MCP, evals/MLOps, cost model, and a recommended architecture.
**Confidence tags:** [H] = primary source checked this session, [M] = secondary source or partial check, [L] = estimate or unverified.
**Method note:** the shared WebSearch budget (200 calls) ran out partway through. After that, claims were checked by fetching primary pages directly (official docs, pricing pages, GitHub READMEs, HF model cards, package registries, paper PDFs) and by checking citations in OpenAlex (45 references checked). The gaps that remain are listed under "Open questions".

---

## 0. TL;DR, and what should change about the product

- **LLM cost is no longer the constraint; evaluation is.** Claude Haiku 5.5 (released ~Oct 7 2026) costs **$0.10 / $0.50 per MTok** ($0.05 / $0.25 on Batch) [H]. Summarizing 5k stories a day costs about **$29–38/month** on Batch. That is the same as or cheaper than self-hosting gpt-oss-20b on a rented L4 (estimated ~$35–49/month [L]), with far less ops work and probably better quality (to be measured). Self-hosting an LLM for this workload is a learning exercise, not a cost saving.
- **Embeddings are cheap in every configuration** ($0–22/month for 300k articles/day). The real decision is *which model clusters news stories well across languages*, and only our own benchmark answers that.
- **The ML centerpiece should be an evaluated, real-time multilingual story-clustering engine**, measured on the Miranda et al. 2018 benchmark. Published scores there are monolingual F1 94.1 (EN) / 97.1 (DE) / 94.2 (ES) and crosslingual F1 84.0 [H]. Modern multilingual embeddings make the crosslingual number a realistic target to beat.
- **Product direction:** make **"Perspectives" (how different countries cover the same story)** the signature AI feature, tied to the Lens: *inside view vs outside view* of any region. This is distinctive, it is backed by existing research (framing taxonomies, SemEval tasks), and it is geo-native. Most aggregators compare left/right bias inside one media system [L — competitor features not re-verified].
- **Data sources to avoid:**
  - ACLED's Open tier gives only aggregated data, with no API, and its terms restrict substitute products [H]. **[verified 2026-10-28: myACLED automatically puts accounts registered with a generic address such as gmail.com in the Open tier, so a solo developer should plan on Open access]**
  - NLLB is CC-BY-NC, and its card calls it "not released for production" [H].
  - Jina v4/v5 are non-commercial [H].
  - TimesFM 3.0 weights are non-commercial [H].
  - Microsoft GraphRAG is in maintenance mode [H].
  - KuzuDB was archived on 2025-10-10 [H].
- **Copyright hygiene doubles as cost control:** store only title + lede + URL, summarize from those, and link out. v1 stored full article text.

---

## 1. Multilingual embeddings & rerankers (a)

| Model | Params | Dims (MRL) | Ctx | Langs | License | Reported multilingual score | Fit for GlobaLens |
|---|---|---|---|---|---|---|---|
| **harrier-oss-v1-270m** (Microsoft, ~Mar 2026) | 270M | 640 | 32k | 94 | MIT [H] **[verified 2026-10-28: the 270m card itself is tagged `license:mit`, so this is no longer an assumption]** | MTEB v2 multi 66.5 (vendor) [H] | **Top CPU candidate** |
| harrier-oss-v1-0.6b / -27b | 0.6B / 27B | 1024 / 5376 | 32k | 94 | MIT [H] | 69.0 / 74.3 (27B leads MMTEB per Oct-2026 roundups [M]) | 0.6B is the GPU ceiling; 27B is too big |
| **EmbeddingGemma 2** (2026-10-06) | 740M multimodal; ~270M text path | 768→128 | 8k | 100+ | Apache-2.0 [H] | Big code gains; English text roughly flat vs v1 [M] | Strong CPU candidate |
| EmbeddingGemma (v1) | 308M | 768→128 | 2k | 100+ | Gemma terms (HF tag) [M] | — | Superseded by v2 |
| **Qwen3-Embedding-0.6B** | 0.6B | 32–1024 | 32k | 100+ | Apache-2.0 [H] | MMTEB 64.33 (8B: 70.58) [H] | GPU path |
| BGE-M3 | 568M | 1024 (+sparse, multi-vector) | 8k | 100+ | MIT [M] | MMTEB 59.56 (per Qwen card) [H] | Hybrid-retrieval baseline |
| multilingual-e5-large-instruct / -small | 560M / 118M | 1024 / 384 | 512 | ~100 | MIT [M] | 63.22 (large) [H] | **e5-small = fastest CPU baseline** |
| nomic-embed-text-v2-moe | 475M (305M active) | 768→256 | 512 | ~100 | Apache-2.0 [M] | — | Alternative |
| Snowflake arctic-embed-l-v2.0 | ~568M [L] | 1024→256 | 8k [L] | 74 | Apache-2.0 [M] | — | Alternative |
| Jina v4 / v5-text (Feb 2026) | ~3.8B [L] / 677M & 239M | — | 32k | 119 (v5-small) | **Non-commercial** (Qwen Research / CC BY-NC) [H] | — | **Avoid self-hosting** |

**Rerankers (query-time only):** bge-reranker-v2-m3 (Apache-2.0 [M]; LightRAG's default recommendation [H]) or Qwen3-Reranker-0.6B (Apache-2.0 [M]). jina-reranker-v3 reports BEIR 61.94 vs 56.51 for bge-v2-m3 (vendor figures) but is CC-BY-NC [M]. On MIRACL, bge-v2-m3 scores higher than jina-v3 (69.32 vs 66.83, vendor table) [M]. Benchmark the candidates on our own queries.

**Throughput (back-of-envelope; benchmark before committing) [L]:** encoder cost is roughly 2 × non-embedding params × tokens.
- A 270M-class model has ~100M non-embedding params. At 128 tokens that is ~26 GFLOP per document, or roughly 4–12 docs/s on 4 vCPUs. That is 0.35–1M docs/day, so it handles 300k/day.
- e5-small (~21M non-embedding) runs at roughly 20–60 docs/s.
- A 0.6B model (~0.44B non-embedding) needs ~113 GFLOP per document, so it needs a GPU or many cores.
- Serverless GPU is dominated by cold starts when used for streaming (see §9). Use it for backfills and fine-tuning.

**Pick:** run a bake-off between harrier-270m, EmbeddingGemma 2 (text) and e5-small, with Qwen3-0.6B as the quality ceiling. Score on SemEval-2022 T8 (Pearson) and Miranda (F1). Store 256-d Matryoshka-truncated `halfvec` in pgvector. **The MTEB average does not measure news-story similarity; our own eval decides.**

---

## 2. LLMs & serving options (b)

**Claude (official pricing page) [H]**

| Model | In / Out ($/MTok) | Batch in / out | Cache read | Notes |
|---|---|---|---|---|
| **Haiku 5.5** (`claude-haiku-5-5`) | 0.10 / 0.50 (≤100K-token prompt); 0.50 / 2.50 above | 0.05 / 0.25 | 0.01 | Bulk workhorse |
| Sonnet 5.5 | 2 / 10 | 1 / 5 | 0.10 (0.05×) | Deep dives, LLM-judge |
| Opus 5.5 | 4 / 20 | 2 / 10 | 0.20 | Rarely needed |
| Fable 5.1 | 10 / 50 | 5 / 25 | 0.25 | Not needed |
| Haiku 4.5 (legacy) | 1 / 5 | 0.5 / 2.5 | 0.10 | 10× Haiku 5.5's price |

**Mechanics that matter [H]:**
- **Batch API:** 50% off. A batch holds at most 100k requests or 256 MB. Most finish in under an hour; a batch expires after 24 h; results are kept for 29 days.
- **Caching in batches is best-effort**, so use the 1-hour cache TTL there.
- **Cache write cost:** 1.25× (5-minute TTL) or 2× (1-hour TTL). The minimum cacheable prefix is 512 tokens on Haiku 5.5, Sonnet 5.5 and Opus 5.5 [H]. **[corrected: not every 5.x model. Per the prompt-caching docs, 512 applies to Haiku 5.5, Sonnet 5.5, Opus 5.5, Opus 5, Fable 5/5.1 and Mythos 5/5.1, but Claude Sonnet 5 needs 1,024 tokens (Haiku 4.5 needs 4,096). The recommended Haiku 5.5 / Sonnet 5.5 path, with its 1.5k-token prefix, is unaffected.]**
- **Haiku 5.5 thinks by default** (adaptive thinking, effort `medium`), and thinking tokens bill as output. For bulk jobs, disable thinking (allowed at effort ≤ `high`) or use effort `low`.
- **Keep prompts under 100K tokens** to stay in Haiku's cheap pricing tier.
- **API version 2026-10-21 rejects `temperature`, `top_p` and `top_k`** with a 400. Reproducibility therefore has to come from stored outputs and eval sets, not from setting temperature to 0.
- **Haiku 5.5 has no server-side refusal fallback.** Handle `stop_reason: "refusal"` in the pipeline.

**Cheap-tier competitors [H]:**
- gpt-5-nano: $0.05 / $0.40 (Batch $0.025 / $0.20).
- GPT-6 Luna: $0.10 / $0.50.
- Gemini 2.5 Flash-Lite: $0.10 / $0.40 (Batch $0.05 / $0.20).

The cheap tier is commoditized. Pick on faithfulness, citations and tooling.

**Open weights:**
- **gpt-oss-20b**: Apache-2.0, 21B total / 3.6B active, MXFP4, runs in 16 GB. Serve with vLLM or Ollama [H].
- gpt-oss-120b: Apache-2.0 [M].
- Gemma 4: Apache-2.0, up to ~31B [M]. EmbeddingGemma 2 is "built on Gemma 4 … Apache 2.0" [H].
- Qwen 3.x: ≤27B dense models are Apache-2.0; larger ones use custom licenses [L].
- DeepSeek V4: MIT [L].
- Llama 4: community license [M].

The aggregator roundups for this group disagree with each other, so treat the open-weight details as unverified.

**GPU pricing:**
- Modal [H]: L4 $0.000222/s (~$0.80/h), L40S ~$1.95/h, A100-80GB ~$2.50/h, H100 ~$3.95/h. The Starter plan includes $30/month in free credits.
- Cloud Run L4: ~$0.0001867/s (~$0.67/h) without zonal redundancy [H]. **[verified 2026-10-28 on the live pricing page: $0.0002909/s (~$1.05/h) with zonal redundancy. This is the GPU line item only; vCPU and memory are billed separately on top.]**
- RunPod serverless: billed per second. Flex workers scale to zero; the 16 GB tier is $0.00016/s [M].
- HF Inference Endpoints and Replicate: **not verified** this session.

---

## 3. Story / event detection (c)

**The benchmark to reproduce: Miranda et al. 2018, EMNLP [H] (paper read)**

- **Method:** online clustering.
  - TF-IDF features over tokens, lemmas and entities for title and body.
  - Three timestamp features: time since the newest, mean and oldest document in the cluster, with a Gaussian of σ = 72 h.
  - An SVM-Rank candidate ranker.
  - A separate "SVM-merge" classifier that decides whether to open a new cluster. It raised English F1 from 82.8 (threshold search alone) to 94.1.
  - Monolingual clusters are linked into crosslingual ones through crosslingual embeddings.
- **Data:** derived from Rupnik et al. 2016 (Event Registry).

| Language | Train docs / clusters | Test docs / clusters |
|---|---|---|
| English | 12,233 / 593 | 8,726 / 222 |
| German | 4,043 / 377 | 2,101 / 118 |
| Spanish | 4,527 / 416 | 2,177 / 149 |

- **Metric:** *pairwise* P/R/F1, not B-cubed.
- **Results:**
  - Monolingual F1 94.1 / 97.1 / 94.2, against a CluStream baseline of 79.0 / 89.7 / 78.1.
  - Crosslingual F1 84.0 with English as pivot (72.7 with a global threshold).
  - Timestamp features were decisive.
- **Code and data:** github.com/Priberam/news-clustering, which points to the successor projected-news-clustering (Text2Story 2022).

**Work since (metadata verified in OpenAlex):**
- Dense vs sparse representations: Staykovski et al. 2019.
- Batch multilingual clustering: Linger & Hajaiej 2020.
- Entity-aware contextual embeddings: Saravanakumar et al., EACL 2021.
- USTORY: SIGIR 2023, not KDD.
- SCStory: WWW 2023.
- Time-aware TDT embeddings: Jiang et al., LREC-COLING 2024.
- **Hanley & Durumeric, ACL 2025:** multilingual *Matryoshka* embeddings, where nested dimension prefixes capture story, narrative and theme, with hierarchical clustering. Pearson 0.816 on SemEval-22 T8 [H]. This is the closest blueprint for GlobaLens.
- LLM-in-the-loop work:
  - Episode detection with LLMs: Kargupta et al., ACL 2025.
  - Event-centric cluster summarization: Zhang et al., ACL 2025.
  - LLM + clustering on GDELT: Tarekegn 2024. Its evaluation is weak (an internal stability index only), which is a gap we can fill.

**Datasets:**
- Miranda (EN/DE/ES).
- **SemEval-2022 Task 8:** ~10k article pairs, 18 language combinations, seven similarity dimensions; best system correlation 0.818 [H].
- WCEP (ACL 2020): Wikipedia Current Events clusters plus summaries.
- GlobeSumm (EMNLP 2024): multilingual and cross-lingual multi-document summarization.

**Metrics:**
- Pairwise F1, for comparability with Miranda.
- **B-cubed P/R/F1**, which satisfies the formal constraints in Amigó et al. 2009.
- AMI/ARI.
- Operational: fragmentation rate, assignment latency at p95, and novelty rate.

---

## 4. NER, entity linking, geoparsing (d)

- **GLiNER2** (Apache-2.0, 2025) [H]: schema-driven NER, classification, structured extraction and relations in one encoder, designed CPU-first.
  - Multilingual checkpoints: `gliner2-multi-v1` (~205M) and `gliner2.5-multi-v1` (287M).
  - `GLiNER2.5-multi-Decide` is a classifier we could use for frame tagging (§5).
  - It succeeds GLiNER (NAACL 2024).
- **Entity linking:**
  - ReFinED (NAACL 2022) is efficient but English-centric [M].
  - For multilingual news: generate candidates from the **Wikidata Embedding Project**, Wikimedia's vector-search API over Wikidata (100+ languages, launched 2025-10-01) [H], plus `wbsearchentities` and a local alias table. Then disambiguate with context similarity, a sitelink-popularity prior and type checks, with **LLM adjudication for low-margin cases** (the pattern of OneNet, EMNLP 2024, and ChatEL, LREC-COLING 2024).
  - Evaluate on **Mewsli-9** (Botha et al. 2020: multilingual entity linking over WikiNews, which matches our domain).
- **Geoparsing:**
  - **Mordecai3** (MIT) reports 92.5% exact GeoNames match and 96.7% within 161 km, conditional on correct place-name detection. It is English-only (spaCy trf) and needs Elasticsearch 7.10 with a 2.2 GB index [H]. That is too heavy for a $50 budget, but it works as an offline teacher or eval reference.
  - **Production path:** GDELT's built-in geocodes; LLM-extracted toponyms for each story (name, country, admin-1); resolution against a local GeoNames subset in PostGIS using trigram matching and a population prior.
  - Evaluate per Gritta et al. 2019. The globe needs **admin-1 accuracy**, not street-level.
- **Cost control:** run heavy extraction on **stories (2–5k/day), not articles (300k/day)**. GDELT GKG already provides persons, organizations, themes and locations for each article; it is noisy but costs nothing.

---

## 5. Framing / stance for "Perspectives" + machine translation (e)

**Framing taxonomies and data [H]:**
- **Media Frames Corpus** (Card et al. 2015) defines the frame taxonomy.
- **SemEval-2023 Task 3** covers genre, 14 frames following Card et al., and 23 persuasion techniques, in EN/FR/DE/IT/PL/RU plus surprise languages. Frames are scored by micro-F1.
- **SemEval-2025 Task 10** covers entity roles (Protagonist / Antagonist / Innocent with fine-grained subroles) and narratives, in BG/EN/HI/PT/RU, for the Ukraine–Russia war and climate change.
- **Licensing trap:**
  - Both SemEval corpora are restricted to research use with no redistribution.
  - Task 10 also forbids **exposing trained models through public APIs**.
  - So use them only for offline evaluation. Never train a public model on them. Build an in-house gold set of 100–300 items.
- **Related work:** narrative framing (Frermann et al., ACL 2023), multilingual framing (Akyürek et al. 2020), bias annotations (BABE, Spinde et al. 2021), and a review of media-bias detection (Hamborg et al. 2019).

**Design:**
1. Group a story's articles by source country, using a source registry: domain → country/language, seeded from Wikidata outlet items (P17/P856) [M].
2. For each group, Haiku 5.5 extracts, with source citations:
   - the frame distribution,
   - entity roles,
   - stance toward the main actors,
   - unique claims and omitted facts.
3. Compute cross-country divergence scores.
4. Distill the LLM labels into a small multilingual classifier (GLiNER2.5-multi-Decide or XLM-R) for cheap tagging of every article. Kuzman & Ljubešić (2025) used the same teacher-student approach for IPTC news topics.

**Machine translation:**
- NLLB-200: CC-BY-NC; its card says "not released for production" and "not for documents" [H]. **Avoid.**
- MADLAD-400: Apache-2.0, 3B / 7.2B / 10.7B, 400+ languages [H]. Usable, but slow on CPU.
- WMT24's findings were titled "The LLM Era Is Here but MT Is Not Solved Yet" [H].
- **Pick:**
  - Translate inside the summarization call: English plus the UI language as structured fields.
  - Lazily translate titles shown in the Lens list with Haiku 5.5. The cost is negligible.
  - GDELT already machine-translates 65 languages (98.4% of its non-English volume) [H].

---

## 6. Forecasting & anomaly detection (f)

| System / model | What | License / access | Use |
|---|---|---|---|
| **VIEWS** (Hegre 2019) | Monthly conflict forecasts 1–36 months ahead; country-month and 0.5° grid (Africa/ME). The 2023/24 challenge forecasts fatality *distributions* (JPR 2025) [H] | Open data portal; license **unverified** | External benchmark plus a forecast layer on the globe |
| ACLED CAST | 6-month forecasts [H] | myACLED login; Open tier is aggregated only, no API [H] | Avoid |
| UCDP GED | Event ground truth, GED 26.1, monthly Candidate releases [H] | API token; 5,000 requests/day [H] | Ground truth for backtests |
| **Chronos-2** (2025-10-20) | 120M (small: 28M); univariate, multivariate, **covariates** [H] | Apache-2.0 [H] | **Default TSFM** |
| TimesFM 2.5 / 3.0 (Aug 2026) | 2.5: 200M, 16k context; 3.0: quantiles, covariates [H] | 2.5 weights Apache-2.0; **3.0 weights non-commercial** [H] | 2.5 only **[verified 2026-10-28, with one nuance: the README permits commercial and production use of TimesFM 3.0 through Google Cloud services such as BigQuery ML. The non-commercial restriction applies to downloaded or self-hosted weights.]** |
| Toto 2.0 (Apr 2026) | 4M–2.5B; observability-pretrained [H] | Apache-2.0 [H] | Optional comparison |
| Moirai 2.0 (Aug 2025) | small [H] | README: release is "for research purposes only"; weight license not stated [H] | Avoid in production |

**Honest evaluation protocol:**
1. **Rolling-origin backtests on as-of data vintages.** UCDP revises its figures, and GDELT keeps publishing articles about past events.
2. **Mandatory baselines:** no-change and seasonal-naive models, scored with MASE (Hyndman & Koehler 2006).
3. **Proper scoring:** CRPS (Gneiting & Raftery 2007), plus 50% and 90% interval coverage and PIT histograms.
4. **Head-to-head against VIEWS** on the same country-months.
5. **Normalize GDELT signals** by total volume per country and day (shares, not raw counts). GDELT volume swings with its source coverage [L].

**Anomaly detection (the "Hotspots" layer):**
- STL decomposition with robust (MAD) z-scores as the baseline.
- BOCPD (Adams & MacKay 2007) for change points.
- A "surprise" score: the observed value falls outside Chronos-2's predictive interval.
- Validate retrospectively against UCDP spikes. Precision@k per week is the reported metric.

---

## 7. Agentic RAG, knowledge graphs, MCP, frameworks (g)

**Retrieval:**
- Postgres only:
  - pgvector 0.8.7 (`halfvec` supports HNSW up to 4,000 dims; binary quantization with re-ranking; iterative scans for filtered queries) [H].
  - Full-text search or BM25.
  - **Reciprocal Rank Fusion** (Cormack 2009) to merge the result lists.
  - A reranker over the top 50.
- **PostGIS filter = the Lens**: "what's happening here" becomes a spatial filter, a time window and a semantic query in one call.

**Knowledge graphs:**
- Microsoft GraphRAG: maintenance mode, expensive indexing [H]. **Skip.**
- KuzuDB: archived [H]. **Skip.**
- LightRAG: MIT, active, PostgreSQL backend. Built for static corpora [H].
- Graphiti: Apache-2.0, bi-temporal facts, Neo4j or FalkorDB backends **[corrected: Amazon Neptune is also supported, and the Kuzu backend is deprecated]**. Its MCP server is not production-ready **[corrected wording: the README calls it an experimental "reference implementation" and says not to run it as a production deployment; it has no authentication]**, and ingestion needs an LLM call per episode [H].
- **Pick:** our own story-level temporal knowledge graph in Postgres (entities, stories, edges with valid-time ranges). Graphiti is optional later.

**Grounding:**
- Claude `search_result` blocks: GA on all current models including Haiku 5.5. `cited_text` is not billed as output. Citations are block-granular [H].
- Citations cannot be combined with structured outputs (a 400 error) [M].
  - So bulk summaries use JSON with `source_ids` that are verified afterwards.
  - Agent answers use native citations.
- Score citation quality with ALCE metrics (Gao et al. 2023).

**MCP [H]:**
- Spec 2026-07-28. Governed as an LF Projects LLC project.
- Extensions: **Tasks**, **Skills over MCP**, and **MCP Apps**: interactive UI rendered in sandboxed iframes, supported by Claude, Claude Desktop, VS Code Copilot, M365 Copilot, Goose and Postman. The `ext-apps` repository includes a **CesiumJS globe example**.
- So a *GlobaLens MCP server with a mini-globe MCP App* is realistic.

**Frameworks:**

| Framework | Version (registry) | Verdict |
|---|---|---|
| **Vercel AI SDK** | 7.0.156, Apache-2.0 [H]: `ToolLoopAgent`, typed UI tool parts → generative UI | **Frontend chat and generative map UI** |
| Anthropic SDK Tool Runner | — | **Backend agent loop** (fewest dependencies) |
| Pydantic AI | 2.63.0, MIT [H]: typed outputs, MCP, durable execution (Temporal, DBOS), pydantic-evals | Good Python alternative |
| Claude Agent SDK | Claude Code as a library: file and bash tools, subagents, hooks [H] | Offline "analyst" jobs and dev tooling, **not** web chat |
| LangGraph | 1.2.18, MIT [H] | Too heavy for one developer |
| OpenAI Agents SDK | 0.24.0, MIT [H] | OpenAI-centric; skip |

---

## 8. Evals & MLOps (h)

**Faithfulness:**
- LLM-AggreFact leaderboard [H]:
  - Best entry: 79.5 (27B model).
  - Bespoke-MiniCheck-7B: 77.4.
  - **MiniCheck-Flan-T5-L (0.8B): 75.0**, cheap enough to run on every summary.
  - Claude-3.5 Sonnet: 77.2.
- HHEM-2.1-Open [H]: Apache-2.0, English-only, ~1.5 s per 2k-token input on CPU.
- Other options: SummaC and AlignScore.
- **Because sources are multilingual, check against English source ledes, and spot-check with a Sonnet 5.5 judge.**

**LLM-as-judge:**
- Judges show position, verbosity and self-preference biases (Zheng et al. 2023).
- Use pairwise comparisons with swapped order.
- Report agreement with ~200 human labels (Cohen's κ).

**Retrieval:** nDCG@10, Recall@50 and MRR on a 200-query golden set; RAGAS-style faithfulness and context precision.

**Tools [H]:**
- **promptfoo:** MIT, "now part of OpenAI". Use it for prompt regression in CI.
- **Langfuse:** core is MIT; part of ClickHouse since Jan 2026. The Hobby tier is free: 50k units/month, 30-day retention, 2 users. Self-hosting is heavy.
- **Arize Phoenix:** ELv2, OpenTelemetry via OpenInference, Docker. Fine for personal self-hosting.
- MLflow for embedding and clustering experiments.
- Braintrust, W&B and Evidently: **not verified** this session.

**Drift monitoring:**
- Language and source-country mix.
- Embedding drift: a weekly domain-classifier AUC between reference and current embeddings.
- Novelty rate (new clusters per 1k articles) and the cluster-size distribution.
- JSON or schema failure rate and refusal rate.
- Cost per day.

---

## 9. Cost model (i)

**Assumptions:**
- Embeddings: 120 tokens per article (title + lede).
- Summaries, per story: 1.5k-token cached prefix, 1.8k-token variable input (about 12 ledes), 350 output tokens, thinking off.
- 30.4 days per month.
- Self-host throughput is assumed, not benchmarked [L].
- **[fact-check note 2026-10-28: Anthropic's docs say Haiku 5.5's tokenizer counts the same text as about 30% more tokens than Haiku 4.5. Measure the 120 / 1.5k / 1.8k / 350-token assumptions with the token-counting endpoint. If they were estimated with an older tokenizer, plan on the "+40% tokens" row below, not the base rows. The table's arithmetic was re-derived from the verified prices and matches within rounding.]**

| Workload | Option | 100k–2k/day | 300k–5k/day |
|---|---|---|---|
| **Embed articles** | Self-host on CPU (270M-class model on the pipeline VM) | ~$0–15 (VM-dependent) [L] | ~$0–15 [L] |
| | OpenAI text-embedding-3-small ($0.02/MTok) | $7 | $22 |
| | Gemini embedding-001 (Batch $0.075 / standard $0.15) | $27 / $55 | $82 / $164 |
| | Modal L4 micro-batches every 15 min (cold-start-dominated) | — | ~$39 |
| | Modal L4, one daily backfill run | — | ~$4 |
| **Summarize stories** | **Haiku 5.5 Batch** (cache hit 0–90%) | **$12–15** | **$29–38** |
| | Haiku 5.5 real-time (95% cache hits) | $23 | $57 |
| | Haiku 5.5 Batch with +40% tokens (non-Latin scripts / new tokenizer) | $19 | $47 |
| | gpt-oss-20b on Modal L4, vLLM (compute only → with hourly cold starts) | $14 → $28 | $35 → $49 |
| | Sonnet 5.5 Batch (for scale) | $307 | $768 |
| **Agent Q&A** | Haiku 5.5, ~20k in / 1.2k out per question | $0.0026/question (3k questions ≈ $8) | |
| | Sonnet 5.5 | $0.052/question → needs rate limits | |

**Budget levers:**
1. **Significance gate:** summarize only clusters with ≥3 articles from ≥2 outlets. Most clusters are singletons, so this is the biggest saving.
2. Re-summarize only on material change: ≥30% growth, or a new country joining.
3. Use LLM adjudication at the *cluster-merge* level (~1–3k decisions/day ≈ $3–8/month in Batch), not per article.
4. Run Batch hourly for the long tail, and use real-time calls only for the top ~200 trending stories.

**Steady-state ML spend: ≈ $25–50/month at the high end** of the volume range with the significance gate, and up to ~$70 without it.

---

## 10. Recommended ML architecture

```
GDELT 2.0 (15-min) + curated RSS ──► normalize → URL canon → MinHash near-dup (wire copies) → language ID
        │
        ▼  CPU embedder (harrier-270m | EmbeddingGemma 2, fine-tuned Matryoshka; 256-d halfvec)
  pgvector + Postgres FTS + PostGIS ──────────────────────────────────────────────┐
        │                                                                          │
        ▼  StoryStream online clusterer (per article, <1 s)                        │
   ANN over live cluster centroids (7-day decayed window) → features:              │
   [cos@64/256 dims, BM25 title/lede, entity Jaccard (QIDs), geo overlap (ADM1),   │
    Δt newest/mean/oldest, source diversity] → LightGBM ranker + calibrated         │
    "new-cluster" classifier                                                       │
        │   hourly: merge/split pass (agglomerative over 48 h) + Haiku 5.5 adjudication on borderline merges
        ▼                                                                          │
   Story (event) → Storyline (weeks; coarse Matryoshka dims + entity graph) → Theme │
        ▼  Haiku 5.5 Batch (structured JSON; gate: ≥3 articles, ≥2 outlets)          │
   headline · bullets w/ source_ids · what's new · locations→GeoNames · entities→Wikidata
   · IPTC topic · Perspectives (per-country frames/roles/claims) → MiniCheck verify │
        ▼                                                                          │
   Signals: country/ADM1 daily series → STL/BOCPD/Chronos-2 surprise → Hotspots;   │
            monthly fatalities (UCDP) → Chronos-2 + LightGBM vs VIEWS               │
        ▼                                                                          ▼
   "Ask the Globe": AI SDK v7 UI ⇄ backend agent (Haiku 5.5; Sonnet 5.5 deep mode),
   tools = search_stories (hybrid+RRF+rerank, Lens-scoped), get_story, timeline,
   compare_perspectives, entity, hotspots, forecast, fly_to → search_result citations
   + the same tools exposed as a remote MCP server (2026-07-28) + MCP App mini-globe
   Evals/MLOps: nightly GitHub Actions eval suite · Phoenix/Langfuse traces · MLflow · drift dashboards
```

**Explicitly not justified:**
- C++/Rust in the ML layer: 300k/day is about 3.5 docs/s on average.
- A dedicated vector DB or graph DB.
- Fine-tuning LLMs.
- A self-hosted LLM in production.

---

## Recommendations for GlobaLens 3.0

1. **[MUST] Build StoryStream (online multilingual clustering) as the core ML artifact.**
   - Reproduce Miranda 2018: pairwise and B-cubed F1; monolingual 94.1/97.1/94.2; crosslingual 84.0.
   - Run ablations for time, entity and geo features and for the LLM merge pass.
   - Report docs/s on 4 vCPUs and p95 assignment latency.
2. **[MUST] Use Claude Haiku 5.5 Batch with 1-hour caching for all bulk LLM work.**
   - Thinking off or effort `low`; prompts under 100K tokens; handle refusals.
   - Sonnet 5.5 only for on-demand deep dives and LLM-judge samples.
   - Drop self-hosted LLMs from production; keep gpt-oss-20b in Ollama for offline development and ablations.
3. **[MUST] Ship an eval harness before the features.**
   - Golden sets: Miranda and SemEval-22 T8; 200 retrieval queries; 300 summary-faithfulness labels; 100–300 perspective items; ~200 entity-linking and geo items.
   - Run promptfoo and pytest in CI; publish a public "Model Card / Evals" page in the app.
4. **[MUST] Embedding bake-off, then fine-tune a Matryoshka story-similarity model (GlobaLens-Embed).**
   - Train a ~270M model on SemEval-22 T8 plus Miranda plus LLM-mined hard negatives.
   - Target: Pearson ≥ 0.816–0.818 on the T8 test set. A few GPU-hours on Modal, ~$5–20.
   - Publish on HF Hub only if the data terms allow it.
5. **[SHOULD] Make "Perspectives" (inside vs outside view, per-country framing and claim divergence) the signature AI feature.**
   - Every divergence claim must be cited and checked with MiniCheck.
   - Distill to a small classifier and report the LLM-vs-classifier cost/quality Pareto.
   - SemEval data for offline evaluation only.
6. **[SHOULD] Build "Ask the Globe" plus a GlobaLens MCP server and MCP App (mini-globe).**
   - Lens-scoped hybrid retrieval with RRF and reranking; native citations.
   - nDCG@10 and citation precision/recall reported.
7. **[SHOULD] Add the Hotspots and forecast layers with an honest backtest.**
   - Chronos-2 and LightGBM against no-change and seasonal-naive baselines and against VIEWS.
   - CRPS and interval coverage on as-of vintages. Publish where it loses.
8. **[SHOULD] Run entity linking and geoparsing at story level only.**
   - GLiNER2-multi, then Wikidata Vector DB and search candidates, then Haiku adjudication; evaluate on Mewsli-9.
   - GDELT geocodes plus a PostGIS GeoNames gazetteer, with admin-1 accuracy as the target.
9. **[MUST] Avoid license traps:**
   - Jina v4/v5, NLLB and TimesFM 3.0 weights in production.
   - ACLED event data in a public UI.
   - Training public models on SemEval-2025 T10.
   - Storing full article text.
10. **[COULD] Add a LightRAG or Graphiti comparison against the Postgres temporal KG later**, as a write-up rather than a dependency.

**Sequencing:**
- After the data and infra phases: embeddings + StoryStream + evals.
- Then summaries and EL/geo.
- Then Perspectives.
- Then the agent and MCP.
- Then forecasting.

Each phase is demoable on its own.

**The five most resume-worthy ML components:**
1. StoryStream with benchmark numbers.
2. GlobaLens-Embed, a fine-tuned multilingual Matryoshka model.
3. The Perspectives engine with distillation.
4. Grounded summarization at roughly $0.0002 per story with a faithfulness harness.
5. Hotspot forecasting with honest backtests.

The agentic MCP and globe work adds systems breadth.

### Open questions (not verified this session; search budget ran out)

- Real CPU throughput of harrier-270m, EmbeddingGemma 2 and e5-small (benchmark on the target VM).
- ~~The license of the harrier-270m weights~~ (resolved 2026-10-28: MIT on the 270m card); the license of VIEWS data; the license of UCDP data (believed CC BY 4.0; the UCDP API docs do not state a license).
- ~~Live Cloud Run GPU prices~~ (resolved 2026-10-28: L4 is $0.0001867/s without zonal redundancy and $0.0002909/s with it, GPU line only); HF Inference Endpoints and Replicate prices; Braintrust and W&B free tiers; Evidently status.
- Exact Gemma 4 and Qwen 3.x lineups.
- The current GIFT-Eval standings (the leaderboard page did not load).
- Whether the SemEval-2022 T8 data terms allow publishing a fine-tuned model.
- Competitor features (Ground News and others).

---

## Sources

**Pricing and models**
- Claude pricing: https://platform.claude.com/docs/en/about-claude/pricing
- Claude batch processing: https://platform.claude.com/docs/en/build-with-claude/batch-processing
- Claude search results (citations): https://platform.claude.com/docs/en/build-with-claude/search-results
- Claude API version 2026-10-21 migration: https://platform.claude.com/docs/en/api/migration-2026-10-21
- Claude Haiku 5.5 announcement: https://www.anthropic.com/claude-haiku-5-5
- Claude Haiku 5.5 coverage: https://venturebeat.com/technology/anthropic-launches-claude-haiku-5-5-with-90-api-price-reduction-matching-gpt-6-luna
- OpenAI pricing: https://developers.openai.com/api/docs/pricing
- Gemini pricing: https://ai.google.dev/gemini-api/docs/pricing
- Modal pricing: https://modal.com/pricing
- Cloud Run pricing: https://cloud.google.com/run/pricing
- RunPod serverless pricing: https://docs.runpod.io/serverless/pricing
- gpt-oss-20b: https://huggingface.co/openai/gpt-oss-20b
- Open-weight roundup: https://www.morphllm.com/best-open-source-llm
- Open-weight comparison: https://wavect.io/blog/open-weight-llm-comparison-2026/

**Embeddings and rerankers**
- harrier-oss-v1-0.6b: https://huggingface.co/microsoft/harrier-oss-v1-0.6b
- Harrier release coverage: https://www.marktechpost.com/2026/03/30/microsoft-ai-releases-harrier-oss-v1-a-new-family-of-multilingual-embedding-models-hitting-sota-on-multilingual-mteb-v2/
- Qwen3-Embedding-0.6B: https://huggingface.co/Qwen/Qwen3-Embedding-0.6B
- EmbeddingGemma docs: https://ai.google.dev/gemma/docs/embeddinggemma
- EmbeddingGemma 2 announcement: https://blog.google/innovation-and-ai/technology/developers-tools/embeddinggemma-2/
- EmbeddingGemma 2 coverage: https://www.marktechpost.com/2026/10/06/google-deepmind-releases-embeddinggemma-2-a-740m-open-multimodal-embedding-model-built-on-gemma-4/
- EmbeddingGemma 2 analysis: https://www.eesel.ai/blog/embeddinggemma-2
- jina-embeddings-v4: https://huggingface.co/jinaai/jina-embeddings-v4
- jina-embeddings-v5 announcement: https://jina.ai/news/jina-embeddings-v5-text-distilling-4b-quality-into-sub-1b-multilingual-embeddings/
- nomic-embed-text-v2-moe: https://huggingface.co/nomic-ai/nomic-embed-text-v2-moe
- Snowflake Arctic Embed 2: https://www.snowflake.com/en/engineering-blog/snowflake-arctic-embed-2-multilingual/
- BGE-M3: https://build.nvidia.com/baai/bge-m3/modelcard
- jina-reranker-v3: https://huggingface.co/jinaai/jina-reranker-v3
- Reranker roundup: https://futureagi.com/blog/best-rerankers-for-rag-2026/
- Text Embeddings Inference: https://github.com/huggingface/text-embeddings-inference
- MMTEB paper: https://arxiv.org/abs/2502.13595
- Embedding leaderboard roundup: https://www.premai.io/blog/best-embedding-models-for-rag-2026-ranked-by-mteb-score-cost-and-self-hosting/

**Story detection**
- Miranda et al. 2018: https://aclanthology.org/D18-1483.pdf
- Miranda code and data: https://github.com/Priberam/news-clustering
- Successor repo: https://github.com/Priberam/projected-news-clustering
- SemEval-2022 Task 8: https://aclanthology.org/2022.semeval-1.155/
- Hanley & Durumeric 2025: https://aclanthology.org/2025.acl-long.124/
- Zhang et al. 2025: https://aclanthology.org/2025.acl-long.801/
- Kargupta et al. 2025: https://aclanthology.org/2025.acl-long.1433.pdf
- Tarekegn 2024: https://arxiv.org/abs/2406.10552
- Saravanakumar et al. 2021: https://aclanthology.org/2021.eacl-main.198.pdf
- Linger & Hajaiej 2020: https://arxiv.org/pdf/2004.08123
- USTORY: https://arxiv.org/pdf/2304.04099
- SCStory: https://dl.acm.org/doi/pdf/10.1145/3543507.3583507
- Jiang et al. 2024: http://www.lrec-conf.org/proceedings/lrec-coling-2024/pdf/2024.main-1.1416.pdf
- WCEP: https://www.aclweb.org/anthology/2020.acl-main.120.pdf
- GlobeSumm: https://aclanthology.org/2024.emnlp-main.603.pdf
- Rupnik et al. 2016: https://doi.org/10.1613/jair.4780
- Amigó et al. 2009: https://doi.org/10.1007/s10791-009-9106-z

**NER, entity linking, geoparsing**
- GLiNER2 repo: https://github.com/fastino-ai/GLiNER2
- GLiNER2 paper: https://arxiv.org/abs/2507.18546
- GLiNER: https://aclanthology.org/2024.naacl-long.300.pdf
- ReFinED: https://doi.org/10.18653/v1/2022.naacl-industry.24
- OneNet: https://aclanthology.org/2024.emnlp-main.756.pdf
- ChatEL: http://www.lrec-conf.org/proceedings/lrec-coling-2024/pdf/2024.main-1.275.pdf
- Mewsli-9: https://www.aclweb.org/anthology/2020.emnlp-main.630.pdf
- Wikidata Embedding Project: https://www.wikidata.org/wiki/Wikidata:Embedding_Project
- Mordecai3: https://github.com/ahalterman/mordecai3
- Mordecai3 paper: https://arxiv.org/abs/2303.13675
- Gritta et al. 2019: https://doi.org/10.1007/s10579-019-09475-3

**Framing and translation**
- SemEval-2023 Task 3: https://propaganda.math.unipd.it/semeval2023task3/
- SemEval-2023 Task 3 paper: https://aclanthology.org/2023.semeval-1.317.pdf
- SemEval-2025 Task 10: https://propaganda.math.unipd.it/semeval2025task10/
- Media Frames Corpus: https://www.aclweb.org/anthology/P15-2072.pdf
- Frermann et al. 2023: https://aclanthology.org/2023.acl-long.486.pdf
- Akyürek et al. 2020: https://www.aclweb.org/anthology/2020.acl-main.763.pdf
- BABE: https://aclanthology.org/2021.findings-emnlp.101.pdf
- Hamborg et al. 2019: https://doi.org/10.1007/s00799-018-0261-y
- Kuzman & Ljubešić 2025: https://doi.org/10.1109/access.2025.3544814
- NLLB-200: https://huggingface.co/facebook/nllb-200-distilled-600M
- MADLAD-400: https://huggingface.co/google/madlad400-3b-mt
- WMT24 findings: https://aclanthology.org/2024.wmt-1.1.pdf
- GDELT: https://www.gdeltproject.org/

**Forecasting**
- VIEWS: https://viewsforecasting.org/
- ViEWS (Hegre et al. 2019): https://doi.org/10.1177/0022343319823860
- VIEWS 2023/24 challenge: https://doi.org/10.1177/00223433241300862
- Escalation prediction competition: https://doi.org/10.1080/03050629.2022.2029856
- ACLED CAST: https://acleddata.com/conflict-alert-system/
- ACLED access tiers: https://acleddata.com/myacled-faqs/
- UCDP API: https://ucdp.uu.se/apidocs/
- UCDP GED: https://doi.org/10.1177/0022343313484347
- TimesFM: https://github.com/google-research/timesfm
- Chronos: https://github.com/amazon-science/chronos-forecasting
- Toto: https://github.com/DataDog/toto
- Moirai (uni2ts): https://github.com/SalesforceAIResearch/uni2ts
- GIFT-Eval paper: https://arxiv.org/abs/2410.10393
- GIFT-Eval leaderboard: https://huggingface.co/spaces/Salesforce/GIFT-Eval
- Gneiting & Raftery 2007: https://doi.org/10.1198/016214506000001437
- Hyndman & Koehler 2006: https://doi.org/10.1016/j.ijforecast.2006.03.001
- BOCPD: https://arxiv.org/abs/0710.3742
- POLECAT: https://osf.io/rm5dw/

**RAG, MCP, agents**
- pgvector: https://github.com/pgvector/pgvector
- RRF: https://doi.org/10.1145/1571941.1572114
- Microsoft GraphRAG: https://github.com/microsoft/graphrag
- GraphRAG paper: https://arxiv.org/abs/2404.16130
- LightRAG: https://github.com/HKUDS/LightRAG
- LightRAG paper: https://aclanthology.org/2025.findings-emnlp.568.pdf
- Graphiti: https://github.com/getzep/graphiti
- Zep paper: https://arxiv.org/abs/2501.13956
- KuzuDB: https://github.com/kuzudb/kuzu
- MCP specification: https://modelcontextprotocol.io/specification/latest
- MCP Apps: https://modelcontextprotocol.io/extensions/apps/overview.md
- MCP governance: https://modelcontextprotocol.io/community/governance.md
- Vercel AI SDK: https://github.com/vercel/ai
- AI SDK version (npm): https://registry.npmjs.org/ai/latest
- Pydantic AI: https://github.com/pydantic/pydantic-ai
- Pydantic AI version (PyPI): https://pypi.org/pypi/pydantic-ai/json
- LangGraph version (PyPI): https://pypi.org/pypi/langgraph/json
- OpenAI Agents SDK version (PyPI): https://pypi.org/pypi/openai-agents/json
- Claude Agent SDK: https://code.claude.com/docs/en/agent-sdk/overview
- ALCE: https://aclanthology.org/2023.emnlp-main.398.pdf

**Evals and MLOps**
- LLM-AggreFact leaderboard: https://llm-aggrefact.github.io/
- MiniCheck: https://aclanthology.org/2024.emnlp-main.499.pdf
- HHEM-2.1-Open: https://huggingface.co/vectara/hallucination_evaluation_model
- SummaC: https://doi.org/10.1162/tacl_a_00453
- AlignScore: https://aclanthology.org/2023.acl-long.634.pdf
- LLM-as-a-judge (Zheng et al. 2023): https://arxiv.org/abs/2306.05685
- RAGAS: https://aclanthology.org/2024.eacl-demo.16.pdf
- promptfoo: https://github.com/promptfoo/promptfoo
- Langfuse: https://github.com/langfuse/langfuse
- Langfuse pricing: https://langfuse.com/pricing
- Arize Phoenix: https://github.com/Arize-ai/phoenix

---

## Fact-check (2026-10-28)

**Method:** I tried to refute the 12 claims a build plan would rest on most heavily, using primary sources:
- official docs and pricing pages;
- the GitHub API and repository READMEs;
- the Hugging Face API and model cards;
- the npm and PyPI registries;
- the Miranda et al. paper PDF.

The shared WebSearch budget ran out during this pass, so every check below is a direct fetch of a primary page. None rests on a secondary roundup.

Inline changes are marked two ways:
- **[corrected: …]** where the report was wrong;
- **[verified 2026-10-28: …]** where a claim held but needed a nuance or a higher confidence tag.

**Result:** 11 confirmed, 1 partially true, 0 refuted, 0 unverifiable. The plan's cost, licensing and dependency foundations hold.

| # | Claim | Verdict | Correction / note | Source |
|---|---|---|---|---|
| 1 | Haiku 5.5 (`claude-haiku-5-5`, released Oct 7 2026) costs $0.10 / $0.50 per MTok for prompts up to 100K tokens ($0.50 / $2.50 above), $0.05 / $0.25 on Batch, and $0.01 for cache reads. Sonnet 5.5 is $2 / $10, Opus 5.5 $4 / $20, Fable 5.1 $10 / $50, Haiku 4.5 $1 / $5 | Confirmed | Prices are exact. The new tokenizer counts the same text as ~30% more tokens than Haiku 4.5, so recount the §9 token assumptions (note added in §9) | platform.claude.com/docs/en/about-claude/pricing; platform.claude.com/docs/en/models/haiku-5-5/overview |
| 2 | Haiku 5.5 thinks by default (adaptive, effort `medium`), and thinking can be turned off only at effort ≤ `high`. API 2026-10-21 returns 400 for `temperature` / `top_p` / `top_k`. Haiku 5.5 has no server-side refusal fallback. Citations combined with structured outputs return 400. `search_result` is GA on Haiku 5.5, `cited_text` is not billed, and citations cover whole blocks | Confirmed | None | platform.claude.com/docs/en/api/migration-2026-10-21; .../models/haiku-5-5/whats-new-haiku-5-5; .../build-with-claude/structured-outputs; .../build-with-claude/search-results |
| 3 | Batch API: 50% off; at most 100,000 requests or 256 MB per batch; most finish in under 1 h; a batch expires after 24 h; results are kept 29 days; caching inside batches is best-effort, so use the 1-h TTL | Confirmed | None | platform.claude.com/docs/en/build-with-claude/batch-processing |
| 4 | Cache writes cost 1.25× (5-min TTL) or 2× (1-h TTL), and the minimum cacheable prefix is 512 tokens "on the 5.x models" | Partially true | The multipliers are correct. The 512 minimum holds for Haiku 5.5, Sonnet 5.5, Opus 5.5, Opus 5, Fable 5/5.1 and Mythos 5/5.1, but Sonnet 5 needs 1,024 (Haiku 4.5 needs 4,096). Corrected inline in §2. No effect on the recommended path | platform.claude.com/docs/en/build-with-claude/prompt-caching |
| 5 | Third-party prices: gpt-5-nano $0.05 / $0.40 (Batch $0.025 / $0.20); GPT-6 Luna $0.10 / $0.50; Gemini 2.5 Flash-Lite $0.10 / $0.40 (Batch $0.05 / $0.20); text-embedding-3-small $0.02/MTok; gemini-embedding-001 $0.15 (Batch $0.075); Modal L4 $0.000222/s with $30/month Starter credits; Cloud Run L4 $0.0001867/s without zonal redundancy | Confirmed | The GPT-6 Luna price is its short-context tier. The Cloud Run price covers the GPU only; vCPU and memory are billed on top, and the zonal-redundant L4 is $0.0002909/s. The live Cloud Run check closes an open question | developers.openai.com/api/docs/pricing; ai.google.dev/gemini-api/docs/pricing; modal.com/pricing; cloud.google.com/run/pricing |
| 6 | Pinned versions: pgvector 0.8.7 (`halfvec` HNSW up to 4,000 dims, binary quantization, iterative scans); `ai` 7.0.156 (Apache-2.0) with `ToolLoopAgent`; pydantic-ai 2.63.0 (MIT); langgraph 1.2.18 (MIT); openai-agents 0.24.0 (MIT) | Confirmed | All are the latest releases today. pydantic-ai 2.63.0 and langgraph 1.2.18 shipped on Oct 26–28 2026, so re-pin at implementation time | GitHub tags and README for pgvector/pgvector; registry.npmjs.org/ai/latest; pypi.org JSON for pydantic-ai, langgraph and openai-agents; ai-sdk.dev/docs/agents/overview |
| 7 | KuzuDB was archived on 2025-10-10; Microsoft GraphRAG is in maintenance mode | Confirmed | The Kuzu repo is archived, its README says "We are archiving the KuzuDB project", and its last push was on 2025-10-10. GitHub does not expose the exact archive timestamp. The GraphRAG README says it is "largely in maintenance mode", with no new features or PRs | api.github.com/repos/kuzudb/kuzu; github.com/microsoft/graphrag (README) |
| 8 | License traps: Jina v4 / v5 are non-commercial; NLLB-200 is CC-BY-NC and "not released for production"; TimesFM 3.0 weights are non-commercial, while weights up to 2.5 are Apache-2.0 | Confirmed | Jina v4 uses the Qwen Research License; v5-text-small and -nano are CC-BY-NC-4.0. Nuance added in §6: TimesFM 3.0 may be used commercially through BigQuery ML; only downloaded or self-hosted weights are restricted | HF API and model cards (jinaai/*, facebook/nllb-200-distilled-600M, google/timesfm-3.0-pytorch); google-research/timesfm README |
| 9 | Licenses and specs of the models the plan adopts: harrier-oss-v1 is MIT. EmbeddingGemma 2 (2026-10-06) is Apache-2.0 and built on Gemma 4: 740M total with a 270M text path, 768→128 MRL, 8K context, 100+ languages. Qwen3-Embedding-0.6B is Apache-2.0. Chronos-2 (2025-10-20) is Apache-2.0: 120M, small 28M. Toto 2.0 (Apr 2026) is Apache-2.0: 4M–2.5B. gpt-oss-20b and MADLAD-400 are Apache-2.0. GLiNER2 is Apache-2.0: multi-v1 ~205M, 2.5-multi 287M | Confirmed | harrier-270m's MIT license is now verified on its own card (the report had assumed it), which closes that open question | HF API license tags; huggingface.co/google/embeddinggemma-2; blog.google EmbeddingGemma 2 post; READMEs of amazon-science/chronos-forecasting, DataDog/toto and fastino-ai/GLiNER2 |
| 10 | Data access: ACLED's Open tier is aggregated-only with no API, and its terms restrict substitute products. The UCDP API needs a token and allows 5,000 requests/day; GED is at 26.1, with monthly Candidate releases. GDELT translates 65 languages (98.4% of its non-English volume) and updates every 15 min | Confirmed | Added: myACLED puts generic-email accounts in the Open tier automatically. UCDP's API page states no data license, so CC BY 4.0 remains unverified | acleddata.com/myacled-faqs; ucdp.uu.se/apidocs; gdeltproject.org |
| 11 | Benchmarks: Miranda 2018 reports monolingual F1 94.1 / 97.1 / 94.2 vs CluStream 79.0 / 89.7 / 78.1, crosslingual 84.0 (72.7 with a global τ), SVM-merge raising 82.8 → 94.1, σ = 72 h, pairwise F1, and the dataset splits as tabled. SemEval-22 T8 best system 0.818; Hanley & Durumeric 0.816. LLM-AggreFact: top 79.5 (27B), Bespoke-MiniCheck-7B 77.4, MiniCheck-Flan-T5-L 75.0, Claude-3.5 Sonnet 77.2 | Confirmed | None | aclanthology.org/D18-1483.pdf (Tables 1, 2, 4, 5); aclanthology.org/2022.semeval-1.155; aclanthology.org/2025.acl-long.124; llm-aggrefact.github.io |
| 12 | Ecosystem status: MCP spec 2026-07-28, governed as a Series of LF Projects, LLC. MCP Apps render in sandboxed iframes and are supported by Claude, Claude Desktop, VS Code Copilot, M365 Copilot, Goose and Postman. ext-apps includes a CesiumJS globe example. promptfoo is MIT and "now part of OpenAI". Langfuse's core is MIT, it has been part of ClickHouse since Jan 2026, and its Hobby tier gives 50k units, 30 days and 2 users. Phoenix is ELv2 | Confirmed | MCPJam and Archestra.AI also support MCP Apps. Langfuse's `ee/` directories have a separate license | modelcontextprotocol/modelcontextprotocol `schema/` directory; modelcontextprotocol.io governance and Apps overview pages; ext-apps README; promptfoo README; Langfuse README, LICENSE and pricing page; Arize-ai/phoenix LICENSE |

**Other spot checks beyond the 12:**
- **Graphiti:** it also supports Amazon Neptune, its Kuzu backend is deprecated, and its MCP server is an experimental reference implementation. Corrected inline in §7.
- **HHEM-2.1-Open:** Apache-2.0, about 1.5 s per 2k tokens on CPU. The cross-lingual support on its card belongs to the commercial HHEM-2.3, so "English-only" stands.
- **Mordecai3:** 92.5% exact and 96.7% within 161 km; Elasticsearch 7.10.1; 2.2 GB index; spaCy `en_core_web_trf`.
- **Moirai 2.0 (Aug 2025):** the README says the release is "for research purposes only".
- **Wikidata Embedding Project:** launched 2025-10-01; 100+ languages; public API.
- **§9 cost arithmetic:** re-derived from the verified prices; it matches within rounding.
