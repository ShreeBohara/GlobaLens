# GlobaLens 3.0: Platform, DevOps and Infrastructure Research

*Research date 2026-10-28. Scope: platform and DevOps for a solo-built, production-grade system. Optimized for (1) résumé signal, (2) a baseline of about $50/month or less, (3) real reliability.*

> **Method and confidence.** Prices were checked against official pricing and docs pages where possible. The shared web-search budget ran out partway through. After that, only known official URLs were fetched directly; nothing was searched. **[H]** = verified on a primary source this session. **[M]** = secondary source or an older primary page. **[L]** = prior knowledge, not re-checked (re-verify before committing money). Euro amounts are converted at about 1.15 USD per EUR (approximate). Bracketed numbers such as [12] refer to the Sources list.

## TL;DR: the verdict

- **Kubernetes should not be the core.** Run stateless parts as **Cloud Run services and jobs** (scale to zero; the free tier covers the idle baseline). Put **Cloudflare** in front (DNS, WAF, R2, a Worker API gateway), host Next.js on **Vercel**, use **Neon** Postgres, and put the one memory-hungry stateful piece (ClickHouse, later Valkey) on **one EU ARM server at Hetzner**. Production: about **$20–35/month** plus LLM tokens.
- **ClickHouse Cloud is too expensive to leave running** (~$159–186/month for the smallest Basic unit at 24/7). That is the cost argument for owning one server, and later a small cluster.
- **Kubernetes only in a late "staff-level" phase**: k3s on three Hetzner ARM nodes with Argo CD for the stateful data plane (~$21/month in nodes), Cloudflare Tunnel instead of a paid load balancer, backed by an ADR with cost math. This matches the career report's "no résumé-driven development" rule.
- **OpenTofu over Terraform** (MPL-2.0 and CNCF vs BSL). Same HCL, so "Terraform/OpenTofu" stays accurate on a résumé. Manage **everything as code**, including GitHub settings, Cloudflare, Vercel and Grafana SLOs.
- **CI/CD is the cheapest senior signal.** Actions is free for public repos (including 4-vCPU arm64 runners): keyless OIDC (Workload Identity Federation), SHA-pinned actions audited with zizmor, SBOMs plus SLSA Build L3 attestations, per-PR full-stack previews, a merge queue.
- **One free observability stack**: OpenTelemetry into Grafana Cloud Free (traces, metrics, logs, k6, synthetics, LLM "agent observability") plus Sentry Developer, with a **data-freshness SLO**.
- **2026 landmines**: Hetzner raised prices twice; AWS App Runner closed to new customers; the Trivy scanner itself was compromised (CVE-2026-33634).

## 1. What changed in 2025–2026 that affects the plan

| Change | Why it matters for GlobaLens | Conf. |
|---|---|---|
| **Hetzner repriced twice in 2026.** Apr 1: CX23 €2.99 → €3.99. Jun 15 (new orders/rescales): CX23 €5.49, CAX11 €5.99, CX33 €8.49; **CPX/CCX ×2.4–2.7** (CCX13 €15.99 → €42.99) [7][8] **[corrected: the 15 Jun multipliers are wider than ×2.4–2.7. Germany/Finland: CPX ×2.44–2.75, CCX ×2.13–2.73 (CCX33 and larger only ≈×2.1–2.3). US: CPX ×2.67–3.09. Singapore: ×1.5–2.1. CX/CAX rose about ×1.3–1.4 (CAX21 €7.99 → €10.49). The 1 Apr adjustment is confirmed by Hetzner's statement of 23 Feb 2026 and applied to existing products as well as new orders. €3.99 is confirmed as CX23's price before 15 Jun, but no primary page shows the €2.99 pre-April figure.]** | Still roughly 3–4× cheaper than hyperscaler VMs (my estimate), but **only CX/CAX are bargains**. Prices exclude VAT and IPv4. | H (Jun) / M (Apr) |
| Hetzner egress included per node: **EU 20 TB, US 1 TB, Singapore 0.5 TB** [8] | Stay in the EU; co-locate the stack near Frankfurt or Finland. | M |
| **AWS App Runner closed to new customers on 30 Apr 2026**; AWS points to ECS Express Mode (Fargate plus ALB) [23][24] | No simple scale-to-zero containers on AWS; the ALB is a fixed cost. | H |
| AWS Free Tier for new accounts: **up to $200 credits within a 6-month plan**, replacing 12 months free [22] | Good for a short experiment, not a free baseline. | H |
| **Trivy compromise, 19–20 Mar 2026**: malicious v0.69.4; **76/77 `trivy-action` tags and all 7 `setup-trivy` tags force-pushed**; the payload stole cloud, Kubernetes and CI secrets while the real scan ran [29] **[corrected: the window was longer and covered more versions. The release and tag compromise began 19 Mar, and malicious Trivy v0.69.5 and v0.69.6 Docker Hub images followed on 22 Mar. The same campaign later reached Checkmarx KICS (23 Mar) and LiteLLM (24 Mar).]** | SHA pins, runner egress control, least-privilege tokens. Security tools are attack surface too. | H |
| GitHub Actions: hosted runners **up to 39% cheaper from 1 Jan 2026**; the **$0.002/min self-hosted fee is postponed** (15 Dec 2025); **public repos stay free** [32] | CI costs $0 for a public repo. | H |
| **Auth.js is "now part of Better Auth"**; Better Auth's homepage says it is "joining Vercel" [58] | Better Auth (MIT) is the default pick. | H |
| pnpm defaults `minimumReleaseAge` to **1440 min** and `blockExoticSubdeps` to true [37]; Dependabot has `cooldown` [36] | Built-in defense against npm worms like the Aug 2025 Nx "s1ngularity" attack [38]. | H |
| **Docker Hardened Images are free (Apache-2.0)** with SBOMs and SLSA Build L3 provenance [42] | Near-zero-CVE base images at no cost. | H |
| HCP Terraform's **legacy free plan ended 31 Mar 2026**; free tier is 500 managed resources [27] | Keep state in GCS, not Terraform Cloud. | M |

## 2. (a) Cloud choice: what GlobaLens' workload costs

**Workload assumed:** a Next.js web app; a modular-monolith `api` (FastAPI, which also hosts the agent endpoints); a `worker` for enrichment, embeddings and clustering; an `ingest` job that pulls GDELT every 15 minutes; later, always-on stream consumers (AIS, ADS-B). Plus Postgres with pgvector and PostGIS, ClickHouse, a small cache, object storage for PMTiles, Arrow snapshots and backups, and occasional GPU use.

| Option | Containers | Postgres | ClickHouse | Object storage / GPU | Est. baseline/month | Verdict |
|---|---|---|---|---|---|---|
| **GCP Cloud Run + Neon + one Hetzner server** | Free tier: 180k vCPU-s, 360k GiB-s, 2M requests per month; then $0.000024/vCPU-s and $0.0000025/GiB-s [9] **[H]** | Neon Free, $0 [16] | Self-hosted on a CAX21 (€10.49 ≈ $12) [8] | R2: 10 GB free, $0 egress [4]; Modal: $30/month in credits [19] | **$15–35** | **Pick** |
| GCP only | Same | Neon or Cloud SQL | GCE VM, ~$25–50 **[L]** | GCS; Cloud Run L4 GPU ≈ $0.67/h for the GPU alone [10] **[M]** | $35–60 | Workable but pricier |
| AWS | ECS Express: Fargate + shared ALB, no extra charge for the mode itself [24] | RDS (credits only) | EC2 | S3 | ~$70–100 after credits (ALB, IPv4, Fargate) **[L]** | Over budget |
| Cloudflare only | Workers Paid $5. Containers: 3× `basic` always-on ≈ $30/month (my calculation from [1]). **Ephemeral disk, no autoscaling yet, 1–3 s cold starts** [2] | None (Hyperdrive only connects to an external Postgres) | Not possible without persistent disk | R2, Workers AI | n/a | Use for the edge, not the backend |
| Fly.io | shared-cpu-1x 1 GB = $6.70/month; **no free tier** [20] | Managed Postgres from $38 [20] | VM plus volume at $0.15/GB [20] | Egress $0.02/GB | $45–90 | No |
| Railway | Billed on usage: $20/vCPU-month and $10/GB-RAM-month; Hobby is $5 and includes $5 of usage [21] | Template | RAM-heavy: ~3 GB resident ≈ $30 | Volumes | $45–65 | No (ClickHouse RAM cost) |
| Hetzner + k3s (data plane) | CAX11 €5.99, CX23 €5.49 [7]; LB11 €7.49 [8], or Cloudflare Tunnel at $0 **[L]** | Self-hosted | Self-hosted | Hetzner Object Storage; no GPUs | $20–35 for everything | **Pick for the stateful tier** |

**Analytics store:** ClickHouse Cloud Basic is $0.2181 per unit-hour (1 unit = 2 vCPU + 8 GiB) plus $25.30/TB-month storage [15] **[M]**: about $66/month at 6 h/day, $159–186/month at 24/7 [15] **[M]**. Its $300/30-day trial [15] **[H]** suits load tests, not production.

**GPU bursts:** Modal Starter is $0/month with $30/month in credits; L4 costs $0.000222/s (~$0.80/h) [19] **[H]**, so roughly 30+ free L4-hours a month for batch embeddings and evals. Use Cloud Run GPU only for latency-sensitive on-demand inference.

**Region:** keep everything in one metro to avoid cross-region latency and egress: Hetzner Nuremberg/Falkenstein (or Helsinki), a nearby EU Cloud Run region, Neon `aws-eu-central-1`, Vercel `fra1`. Check that the Cloud Run free tier applies to the chosen region **[L]**.

## 3. (b) Infrastructure as code

| | Terraform 1.15 (Apr 2026) | **OpenTofu 1.13** (Sep 29, 2026; 1.13.2 on Oct 21) | Pulumi |
|---|---|---|---|
| License | BSL 1.1 [26] | **MPL-2.0, CNCF Sandbox (Apr 2025)** [25] | Apache-2.0 engine, SaaS backend |
| Recent features | Variables in module `source`, deprecation flags [26] | Ephemeral values and `enabled` (1.11), dynamic `prevent_destroy` and import by identity (1.12), linting work (1.13), **client-side state encryption** [25] | Real programming languages |
| Résumé signal | Highest keyword | Same HCL; "Terraform/OpenTofu" | Niche |
| **Verdict** | Fine | **Pick** | Skip: HCL is the common language in job descriptions |

**Layout.** Keep state per layer so blast radius stays small:

```
infra/modules/{cloud-run-service,cloud-run-job,wif-github,neon-project,hetzner-node,cf-zone,grafana-slo}
infra/live/bootstrap   # state bucket, KMS key, WIF pool (applied once, locally)
infra/live/prod/{platform,data,apps,edge,observability,github}
infra/live/preview     # shared preview project (PR revisions are tagged, not separate stacks)
```

- **State:** GCS backend (versioning, native locking) plus OpenTofu state encryption with a Cloud KMS key.
- **Workflow:** `tofu plan` comments on every PR; `apply` on merge through a protected `prod` environment; a nightly `plan -detailed-exitcode` opens an issue on drift.
- **Policy as code:** `trivy config` or Checkov (tfsec is folded into Trivy [30] **[M]**), TFLint, and **Conftest/OPA rules on `tofu show -json`** for GlobaLens's own guardrails: every Cloud Run service sets `max_instances`; no public buckets except tiles; required `cost-center` labels; no static IPs, Cloud NAT or global load balancers without an ADR.

## 4. (c) Compute: Cloud Run vs GKE Autopilot vs k3s

| | **Cloud Run** | GKE Autopilot | **k3s on Hetzner** |
|---|---|---|---|
| Idle floor | **$0** (scales to zero) | Cluster fee offset by a ~$74.40/month credit for one cluster **[L]**; pods are billed on requests, ~$60–75/month for 1.5 vCPU/6 GB always-on, plus ~$18 for a load balancer **[L]** | ~€18/month for 3× CAX11 [7] |
| Operations burden | Minimal | Low | You own upgrades, backups and patching |
| Fits | Stateless API, worker, 15-min jobs, previews, canaries | Nothing at this budget | ClickHouse, Valkey and always-on WebSocket consumers |
| Verdict | **Core runtime** | Avoid, or spin up for a demo and tear down | **Staff-level phase only** |

- **GitOps:** Argo CD **v3.5.6** is latest stable (Oct 20, 2026; 3.6 in RC) [47]; Flux **v2.10.0** shipped Oct 26, 2026 [48]. Pick **Argo CD** (demo-friendly UI, stronger keyword, ApplicationSets); Flux if you want native SOPS.
- **Helm vs Kustomize:** Helm to *consume* vendor charts (ClickHouse operator, cert-manager), Kustomize overlays to *compose* your own.
- **Cloud Run rollout:** deploy `--no-traffic --tag` (URL `tag---service-hash.a.run.app`), smoke-test, shift traffic with `update-traffic`; rollback is immediate [11] **[H]**.

## 5. (d) CI/CD with GitHub Actions

**Workflow structure:** reusable workflows `_build-image.yml`, `_deploy-cloudrun.yml` and `_tofu.yml`. The main `ci.yml` runs `turbo run lint test build --affected` **[L]**. One aggregator job, `ci-ok` (`if: always()`), is the *only* required check, so jobs skipped by path filters never block a merge. Workflows also listen for `merge_group` so the merge queue can run checks [34].

| Control | Implementation | Conf. |
|---|---|---|
| Runner cost | Public repos: standard runners free and unlimited, **including arm64 (4 vCPU / 16 GB, `ubuntu-24.04-arm`)** [33], so ARM images for Hetzner CAX build natively, no QEMU. | H |
| Caching | `setup-uv`, `Swatinem/rust-cache`, pnpm store, buildx `type=gha`; Turborepo remote cache is **free on all Vercel plans** or self-hostable [43]. Actions cache: 10 GB/repo, then $0.07/GB-month [31]. | H |
| No long-lived keys | `google-github-actions/auth@v3` with direct WIF; **always add an attribute condition** (owner/repo) [14]. Other vendor tokens go in environment-scoped secrets. | H |
| Action hygiene | SHA-pin every action; run **zizmor** (MIT; template injection, excessive permissions, credential persistence) [41]; harden-runner egress allow-lists **[L]**; `permissions: {}` by default; never `pull_request_target` with checkout (the Nx attack vector) [38]. | H |
| Dependencies | Renovate (monorepo grouping, action digest pinning, `minimumReleaseAge`) **[L]** or Dependabot `cooldown` (uv, cargo, actions, docker, terraform) [36]; pnpm's default release-age delay [37]. | H/M |
| Scanning | CodeQL default setup and secret-scanning push protection (free on public repos) **[L]**; gitleaks-action needs a free license on *org* repos [39]. | H/M |
| Images | Docker Hardened Images base [42]; Trivy or Grype. **If Trivy, pin a known-good SHA** (v0.69.2–0.69.3 and `trivy-action` v0.35.0 were safe as of March 2026) [29] **[corrected: Microsoft also lists `setup-trivy` v0.2.6 as known-good. Avoid v0.69.4 (malicious binary) and v0.69.5–v0.69.6 (malicious Docker Hub images, 22 Mar). The GitLab advisory lists no fixed version.]** | H |
| Provenance | Syft SBOM plus `actions/attest-build-provenance`: **Build L2 by default, L3 from a reusable workflow**, logged to Sigstore's public transparency log [35]. `gh attestation verify` gates `gcloud run deploy`. | H |
| Releases | release-please manifest mode: node, python, rust (cargo-workspace), helm, terraform-module from one PR stream [40]; Conventional Commits on PR titles. | H |
| Merge queue | **Public repos owned by organizations** only [34], so **move the repo to a free GitHub org**. | M |

**Per-PR full-stack previews (about $0):** a Vercel preview; a Cloud Run revision tagged `pr-N` with no traffic, in a separate `globalens-preview` project; a Neon branch (10 per free project, copy-on-write, starting at $0 [16]). Inject the tagged API URL into the Vercel preview and run Playwright plus a k6 smoke test against it. On PR close, remove the tag (stale tags can keep minimum instances running [11]) and delete the branch.

## 6. (e) Monorepo tooling and developer experience

- **Pick: pnpm + Turborepo** (graph and caching), a **uv workspace** for Python (one lockfile, `uv run --package`) [44], and a **Cargo workspace** if Rust is used. Python/Rust packages get a thin `package.json` delegating to uv or cargo so Turborepo can hash and cache them. Services with conflicting Python requirements become separate path-linked projects [44].
- **mise** pins tools (node, pnpm, python, uv, rust, opentofu) and runs tasks, including monorepo tasks [45], replacing nvm, pyenv, direnv and make.
- **Skip Nx, moon and Bazel**: extra concepts and cost not justified at ~50k lines.
- **Local dev:** Docker Compose `develop.watch` with ClickHouse, Postgres (PostGIS, pgvector), Valkey and the `grafana/otel-lgtm` all-in-one image **[L]**. A devcontainer enables one-click Codespaces (120 h/month free, core-scaled, plus 15 GB-month) [46]. Tilt only once k3s arrives.

## 7. (f) Observability

| Backend | Free tier | Fit |
|---|---|---|
| **Grafana Cloud Free** [49] | 10k active metric series; 50 GB each of logs, traces and profiles; 14-day retention; 3 users; **500 k6 virtual-user hours; 100k API + 10k browser synthetic checks; 50k frontend sessions; 30k LLM generations (Agent Observability)**. Pro from $19/month | **Pick.** One stack covers backend, frontend, load tests, uptime and LLM tracing |
| **Sentry Developer** [50] | 1 user, 5k errors, 5M spans, 50 replays, 5 GB logs, 1 uptime monitor, 1 cron monitor. Team $29/month | **Pick** for errors, source maps and release health |
| Honeycomb Free [51] | 20M events/month, 2 triggers, **no SLOs**; Pro from $150/month | Skip |
| Axiom Personal [52] | 500 GB/month ingest, 30-day retention | A good log sink if Loki's 50 GB runs out |
| SigNoz Cloud [53] | Teams from $49/month | Skip (self-hosting is another stateful system) |
| Better Stack Free [54] | 10 monitors and heartbeats, **1 status page**, Slack and email alerts | Use for a public status page |

- **Instrumentation:** OTel SDKs (Python, Node, Rust) export OTLP straight from Cloud Run to Grafana Cloud, no paid sidecar. **Force-flush on SIGTERM**: request-based Cloud Run throttles CPU between requests **[L]**. On the Hetzner server, Grafana Alloy or an OTel Collector scrapes ClickHouse and host metrics.
- **Cardinality budget:** 10k series goes fast once kube-state-metrics arrives. Allow-list metrics; no per-user labels.
- **SLOs in code:** (1) API availability 99.5% over 30 days; (2) p95 for aggregate and tile queries under 300 ms; (3) **data freshness: 99% of 15-min GDELT windows queryable within 30 min**. Multi-window burn-rate alerts to Grafana IRM (3 free users), a written error-budget policy, and a "data is 7 min old" badge in the UI.

## 8. (g) Testing infrastructure

- **End-to-end and visual regression:** Playwright **1.64** (WebMCP APIs, `--shuffle`; test locks in 1.63; WebP snapshots in 1.62) [55]. Deterministic WebGL screenshots need the official Playwright Docker image, SwiftShader software GL, a fixed camera and seed, a frozen clock, and masks over animated regions **[L]**. Shard across runners against every preview.
- **Load:** k6 **v2.3.0** (`--scenario`, `--once`, OTLP output) [56]. Smoke test per PR, nightly load test, thresholds equal to the SLOs; results in Grafana Cloud k6 (500 VUh free).
- **Contract and integration:** the FastAPI-generated OpenAPI spec is the contract: generated TypeScript client, oasdiff breaking-change checks, Schemathesis fuzzing, Testcontainers for ClickHouse and Postgres **[L]**.
- **Light chaos:** Toxiproxy injects latency and timeouts toward ClickHouse and the LLM provider. In the k3s phase, Chaos Mesh game days and a **disaster-recovery drill**: restore ClickHouse from R2 onto a fresh OpenTofu-built node against a documented RTO/RPO **[L]**.

## 9. (h) Security

| Auth option | Free tier | Notes | Verdict |
|---|---|---|---|
| **Better Auth** | Self-hosted, $0 | MIT; 50+ plugins including 2FA, passkeys, organizations and **API Key** [58] | **Pick.** Users live in your own Neon database; no lock-in |
| Clerk | 50k monthly retained users per app | **MFA, passkeys and removing Clerk branding are not on the free plan**; Pro $25/month [57] | Fastest to set up, but paywalls the features worth showing off |
| Supabase Auth | 50k MAU; free projects pause after a week idle | Only makes sense if you use Supabase as the database [17] | Skip |
| Auth.js | n/a | Now part of Better Auth [58] | Skip |

- **Public API:** hashed, prefixed keys from Better Auth's API Key plugin or **Unkey** (free: 1k keys, 150k valid verifications/month) [59]. A **Cloudflare Worker gateway** in front of `*.run.app` does key checks, per-key rate limits (Durable Objects) and edge caching, and gives `api.` a custom domain without a paid Google load balancer **[L]**. The free WAF rate-limit rule (1 rule, IP-based, 10 s period) [5] is only a flood guard.
- **Secrets:** GCP Secret Manager (6 versions free, then $0.06/version/location [9]) mounted into Cloud Run; SOPS+age or Sealed Secrets for k3s. Doppler is unnecessary (free plan: 3 users, 10 projects) [60].

## 10. (i) Frontend hosting for a WebGL app with SSR pages

| | Free tier | Gotchas | Verdict |
|---|---|---|---|
| **Vercel** [61] | Hobby: **non-commercial only**; 100 GB Fast Data Transfer, 1M function invocations, 4 h Active CPU; **can't buy overage** (hard cap). Pro is $20/seat with $20 of usage included and a default $200 spend budget with optional auto-pause | A viral spike can pause the site. Keep large assets off Vercel | **Pick** (best Next.js 16 fidelity, automatic previews) |
| Cloudflare Workers + OpenNext [3][6] | Static assets free and unlimited; 100k requests/day on Free | Worker size limit **3 MiB on Free, 10 MiB on Paid**, so expect to pay $5. Node middleware not yet supported | The fallback; same edge as R2 |
| Firebase App Hosting [9] | Requires the Blaze plan; runs on Cloud Run; 10 GiB egress free, then $0.15–0.20/GiB | Cold starts; egress costs more than R2 | Skip |

**Rule:** large static assets (PMTiles basemap, globe textures, Arrow and Parquet snapshots) go on **R2 behind a Worker**, which has zero egress fees and Class B reads at $0.36/M after 10M free [4]. This matches the frontend report's Protomaps-on-R2 plan.

## 11. (j) Cost guardrails

1. **GCP budgets only alert, and can lag by hours** [12]. Add a hard stop: a **spend-cap budget** where supported (pauses services), or a Pub/Sub notification driving a kill-switch function that sets Cloud Run `max-instances=0` or disables billing [12].
2. **Hard limits everywhere:** Cloud Run `max-instances` 2–5, timeouts, concurrency; job parallelism; Pub/Sub dead-letter queues.
3. **BigQuery:** a custom `QueryUsagePerDay` quota is proactive and stops the whole project when spent [13]; add `maximum_bytes_billed` per job and require partition filters on GDELT tables.
4. **Hygiene:** Artifact Registry cleanup policies (0.5 GB free, then $0.10/GB [9]), log exclusions (50 GiB free, then $0.50/GiB [9]), lifecycle rules on GCS and R2.
5. **Egress traps:** serve heavy assets from R2; avoid Cloud NAT, static IPs, the global load balancer and Serverless VPC connectors **[L]**; avoid Hetzner US/Singapore traffic tiers [8]. For reference: ClickHouse Cloud $0.10–0.15/GB [15], Vercel Pro $0.15/GB [61], Cloudflare Containers $0.025/GB after 1 TB [1].
6. **Vendor safety nets:** Vercel Hobby hard caps; Neon Free suspends instead of billing [16]; Modal Starter has **no environment-level budgets** [19], so cap GPU-seconds/day in code.
7. **LLM tokens are likely the largest variable cost:** per-day and per-session token budgets enforced by app counters.
8. **Visibility:** label every resource, export billing to BigQuery, show a public "this platform costs $X/month" panel.

## 12. Recommended blueprint by maturity

| Stage | Platform components | Est. monthly cost |
|---|---|---|
| **MVP** (phases 1–3) | Vercel Hobby; Cloud Run `api` + `ingest` job (Cloud Scheduler, every 15 min); Neon Free; R2 for PMTiles and snapshots; Cloudflare Free DNS and WAF; GitHub Actions CI with WIF; OpenTofu with GCS state; Sentry and Grafana Free; budgets and `max-instances` | **$0–5**, plus a domain (~$1–2) |
| **Production** (phases 4–7) | Adds: a Hetzner CAX21 (ClickHouse, Valkey, Alloy, stream consumers) reached through **Cloudflare Tunnel with Access service tokens** (no open ports, no NAT) **[L]**; Cloudflare Workers Paid for the API gateway and Protomaps Worker; a `worker` service plus Pub/Sub; Modal for GPU bursts; Better Auth and API keys; per-PR previews; SLOs and a status page; supply-chain attestations; release-please; merge queue; ClickHouse backups to R2 | **$20–35**, plus LLM tokens |
| **Staff-level** (phases 8–10) | Adds: k3s on 3× CAX11 via OpenTofu, Argo CD with Helm and Kustomize, Sealed Secrets or SOPS; Conftest policy gates; canary releases with automatic rollback on SLO burn; Chaos Mesh game days and a timed disaster-recovery drill; drift detection; a FinOps dashboard. Cloud Run keeps the stateless tier | **$40–60.** Destroy and recreate the cluster from code between demos to stay under $50 |

## 13. Product-direction implications

- **Reliability as a feature:** public status page, live freshness badge, SLO dashboard linked from the README.
- **GlobaLens as a platform:** a public developer API with keys, usage metrics and a generated SDK; rate limits protect the bill (as the market report suggests).
- **Open data products:** daily H3-aggregated Parquet snapshots on R2, nearly free thanks to zero egress.
- **A "$0 at idle" story:** everything scales to zero except one €10 server, a strong cost-engineering interview talking point.

## Recommendations for GlobaLens 3.0

1. **MUST: "serverless core + Cloudflare edge + one EU stateful server".** Cloud Run services and jobs, Vercel, Neon, R2, Workers, and a Hetzner CAX21 for ClickHouse, in one EU metro: the only option under ~$35/month that scales to zero and stays reliable.
2. **MUST: everything as code with OpenTofu.** Layered stacks, GCS backend with encrypted state, PR plan comments, gated applies, nightly drift detection, Conftest guardrails, covering GitHub, Cloudflare, Grafana and Vercel too.
3. **MUST: keyless, attested CI/CD.** WIF with attribute conditions, SHA-pinned actions, zizmor, Hardened Images, SBOM plus Build L3 attestations verified before deploy, dependency cooldowns, and an ADR on the Trivy incident.
4. **MUST: per-PR full-stack previews** (Vercel preview, tagged Cloud Run revision, Neon branch) with auto-teardown and Playwright plus k6 smoke tests.
5. **MUST: cost guardrails on day one:** budget kill switch or spend cap, `max-instances`, BigQuery custom quotas, LLM token budgets, cleanup policies, assets on R2.
6. **SHOULD: OpenTelemetry into Grafana Cloud Free plus Sentry**, with three SLOs (including freshness), burn-rate alerts and a public status page.
7. **SHOULD: monorepo** with pnpm, Turborepo, a uv workspace, mise, one `ci-ok` required check, a devcontainer and Compose watch.
8. **SHOULD: a free GitHub organization** for the merge queue, plus release-please manifest mode and Conventional Commits.
9. **SHOULD: Better Auth for users**, its API Key plugin or Unkey for the public API, rate limiting in the Worker gateway, secrets in Secret Manager.
10. **COULD (staff level): k3s with Argo CD for the data plane**, justified by an ADR with the self-hosting cost math, plus chaos game days, a timed DR drill, and the cluster recreated from code for demos.
11. **COULD: canary deploys on Cloud Run** with automatic rollback on SLO burn.
12. **AVOID:** GKE Autopilot or EKS as the core; always-on ClickHouse Cloud; AWS containers (ALB, IPv4, NAT); Cloudflare Containers for state; Fly Managed Postgres ($38); Railway for RAM-heavy services; Hetzner CPX/CCX; Pulumi, Nx, Bazel.

## Sources

1. Cloudflare Containers pricing — https://developers.cloudflare.com/containers/pricing/
2. Cloudflare Containers FAQ — https://developers.cloudflare.com/containers/faq/
3. Cloudflare Workers pricing — https://developers.cloudflare.com/workers/platform/pricing/
4. Cloudflare R2 pricing — https://developers.cloudflare.com/r2/pricing/
5. Cloudflare rate limiting rules — https://developers.cloudflare.com/waf/rate-limiting-rules/
6. OpenNext for Cloudflare — https://opennext.js.org/cloudflare
7. Hetzner price adjustment (15 Jun 2026) — https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/
8. Hetzner 2026 price hikes and traffic allowances (secondary; cites https://www.hetzner.com/pressroom/statement-price-adjustment/) — https://bex.co/blog/2026/10/14/hetzner-2026-price-hikes-traffic-trap
9. Firebase App Hosting costs (Cloud Run, Secret Manager, Logging and Artifact Registry rates) — https://firebase.google.com/docs/app-hosting/costs
10. Cloud Run pricing (GPU rates via search snippet) — https://cloud.google.com/run/pricing
11. Cloud Run rollouts, rollbacks and tags — https://docs.cloud.google.com/run/docs/rollouts-rollbacks-traffic-migration
12. GCP budgets — https://docs.cloud.google.com/billing/docs/how-to/budgets
13. BigQuery custom quotas — https://docs.cloud.google.com/bigquery/docs/custom-quotas
14. google-github-actions/auth — https://github.com/google-github-actions/auth
15. ClickHouse pricing — https://clickhouse.com/pricing · https://clickhouse.com/zh/pricing · https://selfhost.dev/blog/clickhouse-pricing-real-cost-of-running-it/ · https://guides.tinybird.co/blog/tinybird-vs-clickhouse-cloud-cost-comparison
16. Neon pricing — https://neon.com/pricing
17. Supabase pricing (secondary) — https://www.jetadmin.io/blog/supabase-pricing-2026-guide-to-plans-limits-and-real-world-costs/
18. Upstash Redis pricing — https://upstash.com/pricing/redis
19. Modal pricing — https://modal.com/pricing
20. Fly.io pricing — https://docs.fly.io/about/pricing
21. Railway plans — https://docs.railway.com/pricing/plans
22. AWS Free Tier update (Jul 2025) — https://aws.amazon.com/about-aws/whats-new/2025/07/aws-free-tier-credits-month-free-plan/
23. AWS App Runner release notes — https://docs.aws.amazon.com/apprunner/latest/relnotes/welcome.html
24. Amazon ECS Express Mode — https://docs.aws.amazon.com/AmazonECS/latest/developerguide/express-service-overview.html
25. OpenTofu blog and release lifecycle — https://opentofu.org/blog/ · https://endoflife.date/opentofu
26. Terraform 1.15 and license — https://www.hashicorp.com/en/blog/new-in-terraform-115-dynamic-sources-variable-deprecation-and-more · https://en.wikipedia.org/wiki/Terraform_(software)
27. HCP Terraform plans and free-tier changes — https://developer.hashicorp.com/terraform/cloud-docs/overview · https://spacelift.io/blog/terraform-cloud-free-tier
28. Pulumi pricing (aggregator, low confidence) — https://toolradar.com/tools/pulumi/pricing
29. Trivy compromise — https://www.microsoft.com/en-us/security/blog/2026/03/24/detecting-investigating-defending-against-trivy-supply-chain-compromise/ · https://advisories.gitlab.com/golang/github.com/aquasecurity/trivy/CVE-2026-33634/
30. tfsec vs Trivy (secondary) — https://appsecsanta.com/iac-security-tools/tfsec-vs-trivy
31. GitHub Actions billing — https://docs.github.com/en/billing/concepts/product-billing/github-actions
32. GitHub Actions 2026 pricing changes — https://github.com/resources/insights/2026-pricing-changes-for-github-actions
33. GitHub-hosted runners reference — https://docs.github.com/en/actions/reference/runners/github-hosted-runners
34. Merge queue — https://github.blog/changelog/2023-07-12-pull-request-merge-queue-is-now-generally-available/ · https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue
35. Artifact attestations — https://docs.github.com/en/actions/concepts/security/artifact-attestations
36. Dependabot options reference — https://docs.github.com/en/code-security/dependabot/working-with-dependabot/dependabot-options-reference
37. pnpm dependency-resolution settings — https://pnpm.io/settings/dependency-resolution
38. Nx s1ngularity postmortem — https://nx.dev/blog/s1ngularity-postmortem
39. gitleaks-action — https://github.com/gitleaks/gitleaks-action
40. release-please — https://github.com/googleapis/release-please
41. zizmor — https://github.com/zizmorcore/zizmor
42. Docker Hardened Images — https://www.docker.com/products/hardened-images/
43. Turborepo remote caching — https://turborepo.dev/docs/core-concepts/remote-caching
44. uv workspaces — https://docs.astral.sh/uv/concepts/projects/workspaces/
45. mise tasks — https://mise.jdx.dev/tasks/
46. Codespaces billing — https://docs.github.com/en/billing/concepts/product-billing/github-codespaces
47. Argo CD releases — https://github.com/argoproj/argo-cd/releases
48. Flux releases — https://github.com/fluxcd/flux2/releases
49. Grafana Cloud pricing — https://grafana.com/pricing/
50. Sentry pricing — https://sentry.io/pricing/
51. Honeycomb pricing — https://www.honeycomb.io/pricing
52. Axiom pricing — https://axiom.co/pricing
53. SigNoz pricing — https://signoz.io/pricing/
54. Better Stack pricing — https://betterstack.com/pricing
55. Playwright release notes — https://playwright.dev/docs/release-notes
56. k6 releases — https://github.com/grafana/k6/releases
57. Clerk pricing — https://clerk.com/pricing
58. Auth.js and Better Auth — https://authjs.dev/ · https://www.better-auth.com/ · https://github.com/better-auth/better-auth
59. Unkey pricing — https://www.unkey.com/pricing
60. Doppler pricing — https://www.doppler.com/pricing
61. Vercel pricing — https://vercel.com/pricing
62. Tinybird pricing (ClickHouse-based alternative: free plan 10 GB, 1k requests/day) — https://www.tinybird.co/pricing

## Fact-check (2026-10-28)

*An independent pass over the 12 claims the build plan depends on most, each checked against primary sources. The shared web-search budget had run out, so every check is a direct fetch of an official URL. Result: 10 confirmed, 2 partially true, 0 refuted. The two partial claims are corrected inline above, marked **[corrected: ...]**.*

| Claim | Verdict | Correction / nuance | Source |
|---|---|---|---|
| Hetzner repriced twice in 2026. 1 Apr: CX23 €2.99 → €3.99. 15 Jun, new orders and rescales: CX23 €5.49, CAX11 €5.99, CAX21 €10.49, CX33 €8.49, CPX/CCX ×2.4–2.7 (CCX13 €15.99 → €42.99). Prices exclude VAT and IPv4. | Partially true | Every 15 Jun price point is right. The multipliers are wider than stated: DE/FI CPX ×2.44–2.75, CCX ×2.13–2.73; US CPX ×2.67–3.09; SIN ×1.5–2.1. The 1 Apr change is real and also applied to existing products. The €2.99 pre-April CX23 price is unverified. | https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/ · https://www.hetzner.com/pressroom/statement-price-adjustment/ |
| Cloud Run free tier: 180k vCPU-s, 360k GiB-s and 2M requests per month, then $0.000024/vCPU-s and $0.0000025/GiB-s. | Confirmed | These are request-based billing rates. cloud.google.com/run/pricing is not machine-readable, so the figures were taken from Google's Firebase App Hosting cost page, which uses Cloud Run rates. Secret Manager, Logging and Artifact Registry rates in §9 and §11 also match. | https://firebase.google.com/docs/app-hosting/costs |
| ClickHouse Cloud Basic: $0.2181/unit-hour (2 vCPU + 8 GiB) plus $25.30/TB-month. About $66/month at 6 h/day and $159–186/month at 24/7. $300 trial for 30 days. | Confirmed | ClickHouse's own worked example (AWS us-east-1) gives $66.52/month at 6 h/day, and $159.66 compute or $186.27 total at 24×7. The $0.2181 rate is implied ($159.66 ÷ 732 h), not published. **New constraint:** Basic is capped at 8–12 GiB RAM and 1 TB storage. Upgrade the label from [M] to [H]. | https://clickhouse.com/docs/cloud/manage/billing/overview · https://clickhouse.com/pricing |
| OpenTofu 1.13 (29 Sep 2026; 1.13.2 on 21 Oct) is MPL-2.0 and a CNCF Sandbox project (Apr 2025). Terraform 1.15 (Apr 2026) is BSL 1.1. | Confirmed | The 1.13.0 blog post is dated 29 Sep; the GitHub release object is stamped 30 Sep. 1.13.2 is marked "Latest". CNCF accepted OpenTofu on 23 Apr 2025. Terraform 1.15's changelog is dated 29 Apr 2026 (the blog post followed on 13 May). The BSL 1.1 licensor is now IBM, and each version converts to MPL 2.0 after 4 years. | https://opentofu.org/blog/ · https://github.com/opentofu/opentofu/releases · https://www.cncf.io/projects/opentofu/ · https://www.hashicorp.com/en/blog/new-in-terraform-115-dynamic-sources-variable-deprecation-and-more · https://github.com/hashicorp/terraform/blob/main/LICENSE |
| GitHub Actions: standard runners are free and unlimited on public repos, including arm64 at 4 vCPU / 16 GB (`ubuntu-24.04-arm`). Hosted runners are up to 39% cheaper from 1 Jan 2026. The $0.002/min self-hosted fee is postponed. | Confirmed | `ubuntu-26.04-arm` is now also offered. Private-repo arm64 runners are 2 vCPU / 8 GB and metered. The self-hosted fee is postponed with no new date. | https://docs.github.com/en/actions/reference/runners/github-hosted-runners · https://github.com/resources/insights/2026-pricing-changes-for-github-actions |
| Merge queue works only on public repos owned by organizations, so move the repo to a free org. | Confirmed | The GA changelog covers "all public repos owned by organizations", plus any repo on GitHub Enterprise Cloud. Personal-account repos are not eligible. Current docs pages do not restate eligibility. Upgrade the label from [M] to [H]. | https://github.blog/changelog/2023-07-12-pull-request-merge-queue-is-now-generally-available/ |
| Artifact attestations give SLSA Build L2 by default and L3 from a reusable workflow, logged to Sigstore's public transparency log. | Confirmed | Private repos use GitHub's own Sigstore instance, which has no public transparency log. | https://docs.github.com/en/actions/concepts/security/artifact-attestations |
| Trivy compromise, 19–20 Mar 2026: malicious v0.69.4; 76 of 77 `trivy-action` tags and all 7 `setup-trivy` tags force-pushed; secrets stolen while the real scan ran; CVE-2026-33634. Safe: v0.69.2–0.69.3 and `trivy-action` v0.35.0. | Partially true | Every stated fact is right, but the scope is understated. Malicious v0.69.5 and v0.69.6 Docker Hub images followed on 22 Mar. `setup-trivy` v0.2.6 is also listed as known-good. The campaign later hit KICS (23 Mar), LiteLLM (24 Mar) and Bitwarden CLI (27 Apr update). The advisory lists no fixed version. | https://www.microsoft.com/en-us/security/blog/2026/03/24/detecting-investigating-defending-against-trivy-supply-chain-compromise/ · https://advisories.gitlab.com/golang/github.com/aquasecurity/trivy/CVE-2026-33634/ |
| AWS App Runner closed to new customers on 30 Apr 2026. AWS points to ECS Express Mode (Fargate plus ALB, no charge for the mode itself). | Confirmed | Existing customers keep full use, but no new features are planned. | https://docs.aws.amazon.com/apprunner/latest/relnotes/welcome.html · https://docs.aws.amazon.com/apprunner/latest/dg/apprunner-availability-change.html |
| Auth.js is "now part of Better Auth". Better Auth's homepage says it is "joining Vercel". Better Auth is MIT-licensed with 50+ plugins, including API Key. | Confirmed | None. | https://authjs.dev/ · https://www.better-auth.com/ · https://github.com/better-auth/better-auth |
| Grafana Cloud Free: 10k active series; 50 GB each of logs, traces and profiles; 14-day retention; 3 users; 500 k6 VUh; 100k API and 10k browser checks; 50k frontend sessions; 30k LLM generations. Pro from $19/month. | Confirmed | "3 users" means 3 active visualization users, plus 3 IRM users and 3 Assistant users. Agent Observability also includes 25M tokens/month for evals and guards. | https://grafana.com/pricing/ |
| Vercel Hobby is non-commercial only: 100 GB Fast Data Transfer, 1M invocations, 4 h Active CPU, no overage purchase. Pro is $20/seat with $20 of usage included, a default $200 budget and optional auto-pause. | Confirmed | Pro includes 1 TB of Fast Data Transfer, then from $0.15/GB. | https://vercel.com/pricing |

**Also spot-checked (not in the top 12):**

- **Confirmed:**
  - Argo CD v3.5.6 is latest stable (20 Oct; v3.6.0-rc4 on 22 Oct) and Flux v2.10.0 shipped 26 Oct.
  - Neon Free: 10 branches per project and 100 CU-hours; it suspends instead of billing.
  - pnpm docs: `minimumReleaseAge` defaults to 1440 and `blockExoticSubdeps` to true. The page doesn't say which version introduced these defaults.
  - Docker Hardened Images are free under Apache-2.0, with SBOMs and SLSA L3 even on the free tier.
  - Cloudflare Containers: no autoscaling yet, ephemeral disk by default, 1–3 s cold starts.
  - OpenNext Cloudflare: Node middleware is not yet supported; Worker limits are 3 MiB (Free) and 10 MiB (Paid).
  - Clerk: 50k MRU per app; MFA, passkeys and branding removal are Pro-only; Pro is $25/month, or $20/month billed annually.
  - Modal: Starter includes $30/month in credits; L4 is $0.000222/s; there are no environment-level budgets on Starter.
  - Sentry Developer limits match. Team is $29/month, or $26/month billed annually.
  - GCP spend-cap budgets exist and pause supported services until lifted manually. Budget data lags by several hours.
  - Playwright 1.64, 1.63 and 1.62 features match.
  - Actions cache: 10 GB per repo, then $0.07/GB-month.
  - HCP Terraform Free: 500 managed resources.
  - Hetzner LB11: €7.49.
- **Unverifiable this session:**
  - Hetzner per-node traffic allowances (EU 20 TB, US 1 TB, SIN 0.5 TB): no primary page states them.
  - The 31 Mar 2026 end date for HCP Terraform's legacy free plan: not on the overview page.
  - k6 "OTLP output" as a v2.3.0 feature: `--scenario` and `--once` are confirmed, but OTLP is not in the visible release notes.
  - Cloud Run L4 GPU at about $0.67/h: the pricing page is not machine-readable.
