# Research: a $20/month budget, bring-your-own-key AI, and a build done by Claude

Checked 2026-11-13. This report supports `docs/3.0/rethink.md`. It extends the 2026-10-29 research reports in this folder; it does not replace them.

**How it was gathered.** Five research threads ran in parallel on 13 November, one for each of sections A to E. Section F records the checks made the day before. Each was told to prefer primary sources (vendor docs, pricing pages, changelogs, terms) and to mark every claim:

- **confirmed**: read on the primary page on 2026-11-13;
- **secondary**: from a third-party source or a search summary;
- **not verified**: could not be confirmed, so do not design around it without checking.

Prices are USD before tax unless stated. Free tiers change without notice (Oracle halved its free Arm allowance in June 2026), so every number here needs a re-check before it is relied on.

---

## E. Building with Claude Code when Claude writes all the code

Source of truth: the Claude Code documentation index at https://code.claude.com/docs/llms.txt and the pages linked below.

**Claude in CI**
- The official GitHub Action is `anthropics/claude-code-action@v1`. It answers `@claude` in issues and pull requests, turns issues into pull requests, and with a `prompt` input runs unattended on any event, including a schedule. (confirmed: https://code.claude.com/docs/en/github-actions.md)
- It authenticates with an API key or with a subscription token from `claude setup-token` (Pro, Max, Ultra, Team, Enterprise). The docs say subscription-token runs "use your Claude subscription instead of API billing". (confirmed: same page and https://code.claude.com/docs/en/authentication.md)
- Scheduled workflows in a public repository stop after 60 days without repository activity. (confirmed: https://code.claude.com/docs/en/github-actions.md)
- Fixing failed CI and answering review comments automatically is a cloud-session feature that needs the Claude GitHub App; it is not part of the Action. (confirmed: https://code.claude.com/docs/en/claude-code-on-the-web.md)
- The managed "Code Review" product is for Team and Enterprise plans only. (confirmed: https://code.claude.com/docs/en/code-review.md)

**Cloud sessions and scheduled tasks**
- Cloud sessions run on Anthropic's machines, need a claude.ai sign-in, and count against the plan's usage with no separate machine charge. (confirmed: https://code.claude.com/docs/en/claude-code-on-the-web.md)
- Scheduled tasks (formerly "routines") are a research preview on Pro and above. They run on a schedule, by API call or on GitHub events. Per-task run caps were not verified. (https://code.claude.com/docs/en/routines.md)

**Keeping quality high without hand-written code**
- `CLAUDE.md` is loaded every session and is advisory only; keep it under about 200 lines. (confirmed: https://code.claude.com/docs/en/costs.md)
- Hooks are enforceable. A Stop hook can refuse a "done" claim until the tests pass (it gives up after 8 blocks in a row). A PreToolUse `deny` holds in every permission mode. (confirmed: https://code.claude.com/docs/en/hooks-guide.md, https://code.claude.com/docs/en/hooks.md)
- Subagents have their own context and tools. Workflows script up to 16 concurrent agents and 1,000 per run. (confirmed: https://code.claude.com/docs/en/sub-agents.md, https://code.claude.com/docs/en/workflows.md)
- `/code-review ultra` is a multi-agent cloud review that verifies its findings: 5–15 minutes, at most 500 files or 8,000 changed lines, 3 free runs per account and then roughly $5–25 a run in usage credits. (confirmed: https://code.claude.com/docs/en/ultrareview.md)
- Auto-fix on pull requests pushes clear fixes and asks about unclear ones. Anthropic warns that its comments can trigger comment-driven automation such as Atlantis or Terraform Cloud. (confirmed: https://code.claude.com/docs/en/claude-code-on-the-web.md)

**Looking at the running app**
- The desktop app's Browser pane starts the dev server, takes screenshots, reads the page and clicks through it; automatic verification is on by default. (confirmed: https://code.claude.com/docs/en/desktop.md)
- Claude in Chrome reads console logs, clicks, records GIFs and tests localhost, in a visible browser on the owner's machine. (confirmed: https://code.claude.com/docs/en/chrome.md)
- The docs do not cover Playwright in CI; that part is ordinary engineering.

**Usage limits**
- Pro and Max have a five-hour session limit and a weekly limit, shared between Claude and Claude Code. Setting `ANTHROPIC_API_KEY` switches Claude Code to API billing. (confirmed: https://support.claude.com/en/articles/11145838-using-claude-code-with-your-pro-or-max-plan)
- `--max-turns` and `--max-budget-usd` cap a headless run. (confirmed: https://code.claude.com/docs/en/costs.md)

**Letting Claude deploy**
- Deny rules in `settings.json` and PreToolUse hooks can block commands such as `tofu apply`. The sandbox covers shell commands only and the docs say not to treat it as protection against a malicious command. (confirmed: https://code.claude.com/docs/en/permissions.md, https://code.claude.com/docs/en/sandboxing.md)
- For CI credentials Anthropic recommends Workload Identity Federation (OIDC) over static keys. (confirmed: https://platform.claude.com/docs/en/manage-claude/authentication)
- The docs do not say which steps must stay with a person. Keeping account creation, 2FA and payment with the owner is our policy.

**Inside the product**
- A browser-based bring-your-own-key chat agent should use the Messages API with tool use. The Agent SDK starts a `claude` command-line process and cannot run in a browser. (confirmed: https://code.claude.com/docs/en/agent-sdk/hosting.md)

---

## A. Bring-your-own-key and "bring your own assistant"

**Claude API straight from the browser**
- It works, with the request header `anthropic-dangerous-direct-browser-access: true` (the TypeScript SDK sets it when `dangerouslyAllowBrowser: true`). A cross-origin preflight succeeded on 2026-11-13. Anthropic's docs still recommend a backend. (confirmed: https://platform.claude.com/docs/en/manage-claude/authentication)
- Organisations with zero data retention or the Compliance API get a 401 ("CORS requests are not allowed for this Organization") even with the header. The UI has to explain that error. (confirmed: same page)
- A visitor can make a pasted key low-risk in the Anthropic Console: a dedicated workspace, a key scoped to it, an expiry chosen at creation (3 hours to 30 days), a monthly spend limit on the workspace (not available on the Default workspace), per-model rate limits, and a reversible Disable. Per-key spend caps and per-key model allow-lists were not found. (confirmed: same page and https://platform.claude.com/docs/en/manage-claude/workspaces)
- There is no "Sign in with Claude" for third-party sites. Offering Claude.ai login, or routing requests through Free/Pro/Max/Ultra credentials, is prohibited. (confirmed: https://code.claude.com/docs/en/legal-and-compliance)
- The sanctioned ways to use a visitor's own Claude plan are MCP connectors and AI-powered artifacts, which bill the viewer's plan. (confirmed: https://support.claude.com/en/articles/9487310-what-are-artifacts-and-how-do-i-use-them)

**Other providers** (cross-origin preflights succeeded on 2026-11-13 for OpenAI, Gemini, OpenRouter, Groq and Cerebras)
- OpenRouter still offers its PKCE "connect your account" flow: redirect to `openrouter.ai/auth`, then exchange the code at `/api/v1/auth/keys` for a key the user owns. No app registration step is shown. It charges a 5.5% fee on credit purchases and no markup; free models allow 50 requests a day (1,000 after a $10 purchase). (confirmed: https://openrouter.ai/docs/use-cases/oauth-pkce, https://openrouter.ai/docs/faq)
- OpenAI documents no free allowance. Since 2026-10-28, ChatGPT Pro and Business subscribers can reportedly claim up to $500 a month of API credits. (confirmed: https://developers.openai.com/api/docs/guides/rate-limits; the credits claim is secondary: https://community.openai.com/t/claim-up-to-500-in-api-credits-using-your-chatgpt-pro-or-business-subscription/1410579)
- Gemini has a free tier, but its limits are not published, free-tier content trains Google's models, and only paid tiers may serve users in the EEA. (confirmed: https://aistudio.google.com/docs/pricing, https://aistudio.google.com/docs/terms)
- Groq's free plan allows 30 requests a minute and 1,000 a day. Cerebras has no standing free tier. (confirmed: https://console.groq.com/docs/rate-limits, https://inference-docs.cerebras.ai/support/rate-limits)
- An "OpenAI-compatible endpoint" adapter is still the common denominator for everything except Claude. Anthropic's own OpenAI-compatible layer is meant for testing (no prompt caching), so Claude needs the native adapter. (confirmed: https://platform.claude.com/docs/en/api/openai-sdk)
- Local models: a hosted HTTPS page can reach Ollama or LM Studio on localhost in Chrome 142+ and Firefox 153+ after a permission prompt, and the user must set `OLLAMA_ORIGINS`. Safari still blocks it as mixed content. (confirmed: https://developer.chrome.com/blog/local-network-access, https://www.firefox.com/en-US/firefox/153.0/releasenotes/, https://bugs.webkit.org/show_bug.cgi?id=171934, https://docs.ollama.com/faq)

**Free AI on the visitor's device**
- Chrome's Translator, Language Detector and Summarizer APIs have been stable since Chrome 138, and the Prompt API since 148. All are desktop-only and need about 22 GB of free disk plus more than 4 GB of video memory or 16 GB of RAM. The Translator covers 39 languages; the Prompt API handles only English, Japanese, Spanish, German and French; neither runs in a Web Worker. (confirmed: https://developer.chrome.com/docs/ai/built-in-apis, https://developer.chrome.com/docs/ai/prompt-api, https://developer.chrome.com/docs/ai/translator-api)
- Edge's Prompt API is still a preview behind a flag. Safari and Firefox ship nothing, and both engines have taken negative positions on the Prompt API. (confirmed: https://learn.microsoft.com/en-us/microsoft-edge/web-platform/prompt-api, https://github.com/WebKit/standards-positions/issues/495, https://github.com/mozilla/standards-positions/issues/1213)
- The share of visitors whose machines qualify was not found.

**MCP: the visitor's own assistant does the asking**
- Claude accepts custom remote MCP servers on every plan. The Free plan gets one; paid plans state no cap; servers without login are allowed. (confirmed: https://support.claude.com/en/articles/11175166-getting-started-with-custom-connectors-using-remote-mcp)
- ChatGPT accepts custom MCP servers on the web, reportedly in full only for Business, Enterprise and Edu; Free and Plus are unconfirmed. (confirmed: https://developers.openai.com/api/docs/guides/custom-mcp-server; plan limits secondary: https://help.openai.com/en/articles/12584461-connecting-custom-mcp-servers-in-chatgpt)
- The Gemini app supports them only for US adults on personal accounts, in English. (confirmed: https://support.google.com/gemini/answer/17209137)
- Places to be listed: the official MCP Registry (preview, free, namespaced by GitHub or DNS); Claude's connector directory (the submitter needs a paid Claude plan, tool annotations, a privacy policy and a support contact); ChatGPT's directory (needs a verified identity). (confirmed: https://modelcontextprotocol.io/registry/about, https://claude.com/docs/connectors/building/submission, https://developers.openai.com/apps-sdk/app-submission-guidelines)

**Keeping a pasted key safe**
- The IETF's guidance for browser-based apps (`draft-ietf-oauth-browser-based-apps`, reported by the research thread as published in August 2026) says no browser storage stops malicious JavaScript: a non-extractable WebCrypto key only prevents export, and a worker still lets an attacker send requests. So the key lives in memory by default and persistence is opt-in. (confirmed: https://datatracker.ietf.org/doc/draft-ietf-oauth-browser-based-apps/)
- A Content Security Policy protects only as far as its loosest directive: start from `default-src 'none'` and allow `connect-src` only to our own hosts and the chosen provider. Third-party scripts are the main risk (the polyfill.io compromise reached 100k+ sites). (confirmed: https://w3c.github.io/webappsec-csp/, https://sansec.io/research/polyfill-supply-chain-attack)
- Known incidents: a BYOK Chrome extension leaked 459 OpenAI keys; in Open WebUI (CVE-2025-64496) a malicious OpenAI-compatible endpoint ran script and stole tokens. So anything a custom endpoint returns is untrusted text. No case of key theft by XSS from a mainstream BYOK web app was found. (confirmed: https://www.obsidiansecurity.com/blog/small-tools-big-risk-when-browser-extensions-start-stealing-api-keys, https://github.com/advisories/GHSA-cm35-v4vp-5xvx)
- Whether a stateless proxy or a direct browser call earns more trust has no authoritative answer. Our judgement: direct, because we can then say truthfully that the key never reaches our servers.
- How well-known open-source apps store keys (read from their source): NextChat in plain IndexedDB; big-AGI in localStorage; LobeChat and LibreChat on the server, encrypted.

**Visitors who will not paste a key**
- Patterns in use: cached answers replayed as a simulated stream; a sign-in where the user pays (OpenRouter; Puter.js); an access code. (confirmed: https://ai-sdk.dev/docs/advanced/caching, https://docs.puter.com/user-pays-model/)
- No published figure was found for the share of visitors who enter a key. Plan as if it is small.
- Ways to cap an owner-funded allowance: Cloudflare Turnstile (free, unlimited challenges); a per-IP limiter; Cloudflare AI Gateway dollar budgets; our own governor. Anthropic's own spend limits are monthly only. (confirmed: https://developers.cloudflare.com/turnstile/plans/, https://ai-sdk.dev/docs/advanced/rate-limiting, https://developers.cloudflare.com/changelog/product/ai-gateway/)

---

## B. Free and near-free infrastructure, and compute by the hour

Marks: **C** = confirmed on the primary page on 2026-11-13; **C\*** = primary page read through a fetch summariser; **S** = secondary; **U** = could not verify. EUR→USD uses the ECB rate of 2026-11-13, 1.1052. Converted figures and scenario totals are arithmetic on those inputs.

**Corrections to earlier research**
- OVH US re-cut its range between 12 and 13 November. 4 vCore / 8 GB / 75 GB NVMe is now "VPS-2 2027": $8.50 a month with 12 months paid upfront ($102), $9.50 on 6 months, $10.00 month to month. The $6.46 price belonged to "VPS-1 2026", which has lost its order-page tags. The new VPS-1 is 2 vCore / 4 GB / 40 GB at $4.54–5.35. (C: https://us.ovhcloud.com/vps/)
- Stale in `platform.md` and master-plan §14: the Worker bundle limit (now 64 MiB on both plans), EUR/USD 1.15 (now about 1.105), and free Hugging Face CPU Spaces (withdrawn).

### B1. Cloudflare

| Item | Free plan | Workers Paid ($5/month minimum) |
|---|---|---|
| Worker requests | 100,000 a day, then error 1027 | 10M a month, then $0.30/M |
| CPU time | 10 ms per invocation | 30M CPU-ms a month; up to 5 min a request |
| Worker bundle | 64 MiB uncompressed (since 2026-09-04) | same |
| Static assets | free, unlimited requests; 20,000 files per version; 25 MiB per file | 100,000 files |
| Cron Triggers | 5 per account | 250 |
| Durable Objects | SQLite-backed only; 100,000 requests a day; 5 GB | 1M requests a month, then metered |
| D1 | 5M rows read and 100,000 written a day; 5 GB; hard errors at the limit since 2026-09-01 | 25B read, 50M written a month |
| KV | 100,000 reads and 1,000 writes a day; 1 GB | 10M reads, 1M writes a month |
| Queues | 10,000 operations a day (on Free since 2026-02-04) | 1M a month |
| Vectorize | 5M stored dimensions (about 4,900 vectors at 1,024 dimensions) | 10M stored |
| Workers AI | 10,000 neurons a day, then errors | same, then $0.011 per 1,000 neurons |
| Turnstile | free; unlimited challenges; 20 widgets | — |
| Tunnel | available on all plans | — |
| Cache Rules | 10 rules | — |
| Largest cacheable file | 512 MB | — |

(C: https://developers.cloudflare.com/workers/platform/pricing/, https://developers.cloudflare.com/workers/platform/limits/, https://developers.cloudflare.com/durable-objects/platform/pricing/, https://developers.cloudflare.com/d1/platform/limits/, https://developers.cloudflare.com/kv/platform/limits/, https://developers.cloudflare.com/queues/platform/limits/, https://developers.cloudflare.com/vectorize/platform/pricing/, https://developers.cloudflare.com/turnstile/plans/, https://developers.cloudflare.com/tunnel/, https://developers.cloudflare.com/cache/how-to/cache-rules/, https://developers.cloudflare.com/cache/concepts/default-cache-behavior/)

- **Workers AI inside the free 10,000 neurons a day:** `bge-m3` multilingual embeddings cost 1,075 neurons per million tokens (about 9.3M tokens a day free); `m2m100-1.2b` translation costs 31,050 per million tokens (about 0.32M tokens a day); small LLMs such as `llama-3.2-1b` and `granite-4.0-h-micro` are included. (C: https://developers.cloudflare.com/workers-ai/platform/pricing/)
- **R2 above its free tier:** Standard $0.015/GB-month, Class A $4.50/M, Class B $0.36/M. Infrequent Access $0.01/GB-month with a 30-day minimum, a retrieval fee and no free tier. (C: https://developers.cloudflare.com/r2/pricing/)
- **Terms (updated 2026-09-28):** large files must be served through the Developer Platform, which names R2. So Parquet and PMTiles belong in R2 on a custom domain, not behind a proxied origin. Whether a $0 R2 subscription counts as a "paid service" is not spelled out (U). (C: https://www.cloudflare.com/service-specific-terms-application-services/, https://www.cloudflare.com/service-specific-terms-developer-platform/)
- **Caching large data files:** `.parquet` and `.pmtiles` are not cached by default, so a Cache Rule is needed. An object over 512 MB is never cached, so every range request against it is an R2 Class B read. For a cacheable object of at most 512 MB on an R2 custom domain, Cloudflare fetches the whole file once and then serves ranges from the cached copy. That cache hits are free of Class B charges is an inference (hits never reach the bucket), not a statement in the docs. (C: https://developers.cloudflare.com/cache/reference/range-requests/)
- **Spend control:** dollar spending limits launched on 2026-11-13 for Workers and Durable Objects only, and "a limit does not guarantee a maximum invoice amount". R2, KV, D1 and Workers AI have email alerts only. Free-plan quotas return errors instead of billing; R2 overage is billed. (C: https://developers.cloudflare.com/billing/manage/spend-management/, https://developers.cloudflare.com/billing/manage/budget-alerts/)

### B2. An always-on server near 4 vCPU / 8 GB

| Provider, plan | vCPU / RAM / disk | Monthly (USD) | Hourly billing | Notes | Mark |
|---|---|---|---|---|---|
| OVH US VPS-2 (2027) | 4 / 8 GB / 75 GB NVMe | $10.00 monthly; $9.50 on 6 months; $8.50 on 12 months ($102 upfront) | no | US-East, US-West; daily backup included; OpenTofu provider `ovh/ovh` | C |
| OVH US VPS-1 (2027) | 2 / 4 GB / 40 GB NVMe | $4.54–5.35 | no | same | C |
| Hetzner CX33 | 4 shared / 8 GB / 80 GB NVMe | €8.99 = $9.94 | yes | **"not available" today**; EU only | C |
| Hetzner CAX21 (Arm) | 4 shared / 8 GB / 80 GB NVMe | €10.99 = $12.15 | yes | **"not available" today** | C |
| Hetzner CPX32 | 4 shared / 8 GB / 160 GB NVMe | €30.49 = $33.70 (Helsinki) | yes | the cheapest orderable Hetzner 8 GB plan | C |
| netcup VPS Lite 2 | 4 shared / 8 GB / 160 GB SSD | €9.50 incl. 19% VAT = $10.50 | no | 3-month term; location not selectable; no OpenTofu provider found | C |
| Contabo Cloud VPS 4 | 4 shared / 8 GB / 100 GB SSD | €5.50 = $6.08 plus a setup fee | no | €4.40 on 24 months | C |
| Contabo Cloud VPS 6 | 6 shared / 12 GB / 100 GB NVMe | €7.50 = $8.29 | no | €6.00 on 24 months | C |
| Hostinger KVM 2 | 2 / 8 GB / 100 GB NVMe | $8.79 with 24 months prepaid; renews at $14.99 | no | | C |
| DigitalOcean, Vultr, Akamai | 4 shared / 8 GB | $40–48 | yes | reference only | C / C\* |

(Sources: https://us.ovhcloud.com/vps/, https://www.hetzner.com/cloud/cost-optimized, https://www.hetzner.com/cloud/regular-performance, https://www.netcup.com/en/server/vps-lite, https://contabo.com/en/vps/, https://www.hostinger.com/vps-hosting, https://www.digitalocean.com/pricing/droplets)

### B3. Compute by the hour (CPU only)

| Provider | 8 vCPU / hour | 16 vCPU / hour | Billing | 3 nodes × 8 vCPU × 6 h | 16 vCPU × 48 h | Mark |
|---|---|---|---|---|---|---|
| Hetzner shared (CPX42, CPX62) | €0.0953 | €0.1779 | per started hour, until deleted | $1.90 | $9.44 | C |
| Hetzner dedicated (CCX33, CCX43) | €0.1891 | €0.3766 | same | $3.76 | $19.98 | C |
| DigitalOcean | $0.143–0.25 | $0.50 | per second | $2.57–4.50 | $24.00 | C |
| Scaleway | €0.1034–0.2128 | €0.2067–0.4256 | per hour | $2.06–4.23 | $10.97–22.58 | C |

- Both scenarios together cost about $11 on Hetzner shared cores. Hetzner raises a new account's limits only "if you have been with us for a month and paid your first invoice", so the account must be opened well before launch week. (C: https://docs.hetzner.com/cloud/billing/faq/, https://docs.hetzner.com/cloud/servers/faq/)
- Modal's free $30 a month covers about one 48-hour 8-core job. (C\*: https://modal.com/pricing)

### B4. Free batch compute

- **GitHub Actions on a public repository:** 4 vCPU / 16 GB runners for x64 and arm64, 6 hours a job, 20 concurrent jobs, no monthly cap on standard runners. Schedules can be delayed or dropped under load and are disabled after 60 days without repository activity. (C: https://docs.github.com/en/actions/reference/runners/github-hosted-runners, https://docs.github.com/en/actions/reference/limits, https://docs.github.com/en/billing/concepts/product-billing/github-actions)
- **Its terms (effective 2026-08-27)** forbid using Actions "as a content delivery network or as part of a serverless application" and any activity "unrelated to the production, testing, deployment, or publication of the software project associated with the repository". Our reading: nightly builds of the project's own published dataset are defensible; running the live 15-minute ingest there is not. (C: https://docs.github.com/en/site-policy/github-terms/github-terms-for-additional-products-and-features)
- **GHCR:** public images are free; storage and bandwidth are "currently free". (C: https://docs.github.com/en/billing/concepts/product-billing/github-packages)
- **Kaggle notebooks:** 4 CPU cores and 30 GB RAM for up to 12 hours a session (C: https://www.kaggle.com/docs/notebooks); a GPU quota of about 30 hours a week (S).
- **Hugging Face:** free accounts now get Static Spaces only; ZeroGPU gives 5 GPU-minutes a day. (C: https://huggingface.co/docs/hub/spaces-overview, https://huggingface.co/docs/hub/spaces-zerogpu)

### B5. Free supporting services

| Service | Free limits | Mark |
|---|---|---|
| Neon | 100 CU-hours per project a month, 10 branches per project (enough for pull-request previews), scales to zero, suspends instead of billing | C |
| Grafana Cloud | 10,000 active series; 50 GB each of logs, traces and profiles; 14-day retention; 500 k6 virtual-user hours | C |
| Sentry Developer | 1 user; 5,000 errors; 1 uptime and 1 cron monitor | C |
| Healthchecks.io | 20 jobs (its Business plan is free for open-source projects on request) | C |
| UptimeRobot | 50 monitors at 5-minute intervals | C |
| Tailscale Personal | 6 users, 50 tagged resources, 1,000 ephemeral-node minutes a month (three burst nodes for six hours need 1,080) | C |
| Resend | 3,000 emails a month, 100 a day | C |
| Web Push | no per-message fee | C\* |

(Sources: https://neon.com/docs/introduction/plans, https://grafana.com/pricing/, https://sentry.io/pricing/, https://healthchecks.io/pricing/, https://uptimerobot.com/pricing/, https://tailscale.com/pricing, https://resend.com/pricing, https://webkit.org/blog/12945/meet-web-push/)

Always-free virtual machines other than Oracle's are not usable as a second server: GCP offers one e2-micro; AWS and Azure offer none. (C: https://docs.cloud.google.com/free/docs/free-cloud-features, https://aws.amazon.com/free/free-tier-faqs/)

### B6. Hosting the Next.js frontend for $0

| Option | Limits | What breaks | At the limit | Mark |
|---|---|---|---|---|
| (a) Next.js on Workers Free through OpenNext | 10 ms CPU a request; every server-rendered request counts toward 100,000 a day | Cloudflare says server rendering "typically use[s] 10–20 ms" of CPU, above the free limit | errors 1027 and 1102 | C |
| **(b) Static export on Workers Static Assets** | free, unlimited requests; 20,000 files; 25 MiB a file | no ISR, Server Actions, middleware, rewrites or per-request route handlers; static assets ignore `Range` | no Worker runs, so no daily quota applies | C |
| (c) Vercel Hobby | 1M CDN requests and 100 GB transfer a month | "personal or non-commercial use" only | the site pauses (503) until 30 days pass; no overage can be bought | C |

(Sources: https://developers.cloudflare.com/workers/static-assets/billing-and-limitations/, https://developers.cloudflare.com/workers/framework-guides/web-apps/nextjs/, https://opennext.js.org/cloudflare, https://nextjs.org/docs/app/guides/static-exports, https://vercel.com/docs/plans/hobby, https://vercel.com/legal/terms)

Option (b) is the only one that survives a launch-day spike at $0: static files never invoke a Worker, and data comes from R2 behind the cache. The server re-renders what changes and pushes it to the CDN.

### B7. Too good to rely on

- Hetzner's cheap CX/CAX plans: not orderable today.
- OVH's $8.50: needs $102 upfront, and the page changed within a day.
- Contabo, Hostinger and IONOS headline prices: setup fees, 24-month prepayment, or renewals at 1.7–3 times the intro rate.
- GitHub Actions and GHCR: free at GitHub's discretion; schedules can be dropped.
- Cloudflare's free quotas: D1's limits became hard errors on 2026-09-01; the spending limit is one day old and not a guaranteed cap.
- Vercel Hobby: non-commercial only, and a project can be shut down without notice.
- Oracle's free Arm machine: halved in June 2026; idle instances are reclaimed (checked 2026-11-12).

---

## C. What the visitor's browser can do for free, and UI craft

Every claim was confirmed on 2026-11-13 at the URL beside it unless marked: **M** = measured by the research thread; **U** = unverified.

**Stale in the earlier docs:** MapLibre GL JS is at 6.18.0; deck.gl v10.0.0-alpha.1 shipped on 2026-11-12; the Protomaps planet file is 139 GB. (https://registry.npmjs.org/maplibre-gl, https://github.com/visgl/deck.gl/releases, https://build-metadata.protomaps.dev/builds.json)

**DuckDB in the browser (DuckDB-WASM)**
- npm `latest` is 1.33.1-dev57.0 (DuckDB 1.5.4, M); the `next` tag builds on DuckDB 2.0. Range reads over HTTP use the JavaScript httpfs path, with a 4 GB cap and one thread. (https://registry.npmjs.org/@duckdb/duckdb-wasm, https://duckdb.org/docs/2.0/clients/wasm/overview.html)
- Size and speed (M): the core is 7.1 MB compressed; the spatial extension adds 4.5 MB and h3 under 0.1 MB, and both run. On desktop Chromium the first query returns 1.0 s after a cold start. Phones were not measured, and the iOS memory ceiling is unverified.
- Open problems: a Firefox range-request bug, an OPFS durability bug, and `db.open` failing in private WebKit windows on the `next` build. (https://duckdb.org/docs/2.0/clients/wasm/troubleshoot.html, https://github.com/duckdb/duckdb-wasm/issues/2192, https://github.com/duckdb/duckdb-wasm/issues/2302)
- Public apps built this way report slow first loads (one reports 61.8 s). OpenTimes uses the much lighter hyparquet reader and reports Cloudflare evicting large files. (https://marchenco.pages.dev/blog/browser-sql-no-backend-3.html, https://opentimes.org/about/)
- Conclusion: load it lazily, for the decade charts only. Keep it off the first screen.

**WebGPU**
- Available in Chrome 113 (desktop) and 121 (Android), Firefox 141 (Windows) and 147 (macOS) but not Linux or Android, and Safari 26 everywhere: 86.8% of users, plus 3.3% partial. (https://github.com/gpuweb/gpuweb/wiki/Implementation-Status, https://caniuse.com/webgpu)
- deck.gl 9.4.1 calls its WebGPU backend "not production ready" (no basemap interleaving; two filter extensions are WebGL-only). MapLibre closed its WebGPU proof of concept in September 2026. (https://deck.gl/docs/developer-guide/webgpu, https://github.com/maplibre/maplibre-gl-js/pull/7411)
- Conclusion: the globe stays on WebGL2. WebGPU compute is an optional extra for particle fields and million-point aggregation, and each use needs a second, WebGL implementation as the fallback. (https://luma.gl/docs/api-reference/engine/compute/computation)

**Exporting a time-lapse as video, in the browser**
- The WebCodecs `VideoEncoder` is in Chrome 94, Safari 16.4 and desktop Firefox 130 (not Firefox for Android). H.264 Main up to 4K encodes on 98.9% of devices; 10 seconds at 8 Mbps is about 10 MB. (https://developer.mozilla.org/en-US/docs/Web/API/WebCodecs_API/Codec_selection)
- Mediabunny 1.66 (MPL-2.0) replaces mp4-muxer and applies backpressure. MapLibre's `setNow()` freezes time "for frame-by-frame video capture". (https://mediabunny.dev/guide/media-sources, https://maplibre.org/maplibre-gl-js/docs/API/functions/setNow/)
- Known limits: Chrome's encoder slows while the page re-renders; Firefox has open H.264 bugs. (https://www.remotion.dev/docs/mediabunny/webcodecs-bugs)
- An open-source MapLibre export plugin exists, but no well-known globe app was found that offers this. (https://github.com/bjperson/maplibre-gl-video-export)

**Scripted tours**
- Prior art: Mapbox's storytelling template and KML tours. `driver.js` is MIT-licensed; Shepherd and Intro.js are AGPL. (https://github.com/mapbox/storytelling, https://developers.google.com/kml/documentation/touring)
- No public map app was found where one script drives both the tour and the tests. The pieces exist: MapLibre's `setNow` was added for "video export and deterministic testing", and Playwright's `page.clock` controls animation frames. (https://github.com/maplibre/maplibre-gl-js/blob/main/CHANGELOG.md, https://playwright.dev/docs/clock)

**Offline use**
- Storage: Safari 17+ allows about 60% of disk per origin but deletes script-written storage after 7 days without a visit; Chrome allows 60%; Firefox the smaller of 10% or 10 GiB. (https://developer.mozilla.org/en-US/docs/Web/API/Storage_API/Storage_quotas_and_eviction_criteria)
- A Protomaps world basemap is small at low zoom (M): 15 MB for zoom 0–5, 45 MB for 0–6, 190 MB for 0–7.
- The Cache API rejects partial (206) responses, so whole files go into OPFS and are read with the PMTiles `FileSource`. (https://w3c.github.io/ServiceWorker/#cache-put, https://github.com/protomaps/PMTiles/blob/main/js/src/index.ts)

**Web platform features, late 2026** (https://unpkg.com/web-features@3.46.0/data.json)
- Safe everywhere: same-document view transitions, scroll-driven animations (Baseline since 2026-10-27), popover, OffscreenCanvas, Event Timing (so INP is measurable in every browser).
- Use only with a fallback: cross-document view transitions (no Firefox), anchor positioning (the spec is still moving), speculation rules (Chromium), `scheduler.yield` (no Safari), Long Animation Frames (Chromium).
- INP guidance: 200 ms at the 75th percentile; clicks, taps and key presses count, drags and scrolls do not. (https://web.dev/articles/inp, https://web.dev/articles/optimize-long-tasks)

**Share cards**
- A free Worker has 10 ms of CPU per request, too little to draw an image on demand, so cards are pre-rendered in batch. (https://developers.cloudflare.com/workers/platform/limits/)
- `next/og` pins Satori 0.33.5, which has no bidirectional-text support. Satori 0.63 adds simplified bidi and WOFF2; Takumi runs the full bidi algorithm. (https://github.com/vercel/satori, https://takumi.kane.tw/docs/typography)

**Craft references**
- Shopify's BFCM 2025 globe (a 2026 Webby honoree): baked lighting, one mask texture driving about 85 lights, hidden easter eggs. (https://shopify.engineering/2025-bfcm-live-globe)
- Bloomberg's ICE flights map: animation separates overlapping routes and shows direction without arrows. The Pudding's "30 minutes with a stranger": moves between one anecdote and the whole dataset. (https://www.datawrapper.de/blog/data-vis-dispatch-december-23-2025)
- OpenTimes: all-static Parquet that "costs nothing to serve". (https://simonwillison.net/2025/Mar/17/opentimes/)

**Accessibility and mixed scripts**
- MapLibre's canvas is a focusable region with keyboard pan, zoom, rotate and pitch. MapLibre 6.7–6.9 shape Devanagari, Khmer, Burmese, Arabic and Hebrew natively, deprecate the RTL plugin and accept web fonts through `font-faces`. (https://maplibre.org/maplibre-gl-js/docs/API/classes/KeyboardHandler/, https://github.com/maplibre/maplibre-gl-js/blob/main/CHANGELOG.md)
- `dir="auto"` looks only at the first strong character. Set `dir` from the known language and use `<bdi>` otherwise; `lang` also picks the right Han glyph variants. Prefer system CJK fonts: Google serves Noto Sans SC in 101 slices (M). (https://www.w3.org/International/articles/inline-bidi-markup/, https://www.w3.org/International/questions/qa-lang-why)

**Ideas ranked by impact per dollar (all $0 to run)**
1. One seekable tour timeline that drives the live tour, the MP4 export and the Playwright screenshots. Risk: deck.gl has no "idle" event.
2. Time-lapse export in the browser. Risk: no Firefox for Android; slow on phones.
3. Multilingual share cards pre-rendered in batch. Risk: bidi edge cases.
4. Map labels in native scripts. Risk: a code path only months old.
5. `dir` and `lang` on every headline; system CJK fonts. Risk: wrong language codes in the data.
6. An offline "pocket globe": the zoom 0–5 basemap plus the latest day. Risk: Safari's 7-day eviction.
7. DuckDB-WASM, lazily, for decade charts. Risk: a 7 MB download and iOS memory.
8. Cache Rules and Parquet files under 512 MB on R2. Risk: slow first hit on a cold cache.
9. Scroll-driven animations, anchored popovers and view transitions, each with a fallback. Risk: engines differ on anchoring.
10. An iframe embed that shows the share card until clicked. Risk: slows the host page.

---

## D. Multilingual ML on CPUs only

Marks: **C** = primary page fetched on 2026-11-13; **V** = vendor-measured, fetched that day; **E** = our estimate; **U** = unverified. Two quality scores come from the MTEB results repository (https://github.com/embeddings-benchmark/results): **STS22x**, the mean Spearman correlation over the eight cross-lingual pairs of STS22.v2 (news text from SemEval-2022 Task 8), and **NTREX**, bitext-mining F1 on news sentences.

**Which of the plan's choices survive**
- Survive: `multilingual-e5-small` for the whole feed; `harrier-oss-v1-270m` as the higher-quality second pass; pgvector with halfvec and HNSW; Claude Haiku 5.5 through the Batch API, as polish only; CPU translation with Marian models, promoted from the backlog to the main path for English glosses.
- Do not survive: Haiku as the main gloss engine (the real-time, on-view calls); the Qwen3-0.6B "GPU ceiling" and the Modal fine-tune as plan steps; EmbeddingGemma as a co-favourite (NTREX 0.74, and version 1 was the worst encoder on titles-only clustering in the EMNLP 2026 study below); the blanket "ONNX int8" rule (one vendor measured OpenVINO 5.5× faster than ONNX Runtime and reports severe quality loss from int8 transformer weights, V).

**Embeddings**
- The feed needs about 3.5 titles a second. On 4 vCPUs, e5-small manages about 200 titles a second and a harrier-class model about 40 (E). Speed is not the constraint.
- Static embedding models are about 100× faster (107k against 910 sentences a second for a same-shape MiniLM, C: https://huggingface.co/blog/static-embeddings) but fail across languages (NTREX about 0.43), so they suit same-language pre-grouping only.
- transformers.js, the library that runs these models in a browser, is at 4.3.2 (Apache-2.0, released 2026-10-27). (C: https://registry.npmjs.org/@huggingface/transformers)
- The browser must run the same model that built the index, and the model file is 118–130 MB. So search queries are embedded on the server by default (about 10 ms, E); in-browser embedding is optional.

**Translation into English**
- Recipe: Mozilla's Firefox Translations "student" models for the big languages, OPUS-MT family models through CTranslate2 for the rest, and Claude Batch on the top stories.
- Measured: a small student model translates 3,000 sentences (56k tokens) in 16–17 s on one Xeon thread (C: https://github.com/browsermt/students/blob/master/esen/README.md). CTranslate2 4.9.0 runs an OPUS-MT base model at 696 tokens a second on 4 threads (C: https://github.com/OpenNMT/CTranslate2).
- The whole feed, about 212k titles or 5.3M tokens a day (E), takes about one core-hour a day with student models, or two hours on four threads with OPUS-MT base models (E).
- Coverage: Mozilla has 55 released into-English pairs (MPL-2.0, 13–60 MB each, median COMET22 0.861 by Mozilla's own figures, C: https://github.com/mozilla/translations). Helsinki-NLP publishes about 219 into-English models, mostly Apache-2.0 (C: https://huggingface.co/Helsinki-NLP).
- Weak spots on OPUS-MT (chrF on Flores-200, C: https://opus.nlpl.eu/dashboard/): Japanese .487, Somali .445, Burmese .423; there is no Mongolian model. `tencent/Hy-MT2-1.8B` (Apache-2.0) covers Burmese, Khmer, Mongolian and Kazakh, and `google/madlad400-3b-mt` (Apache-2.0) the rest; their CPU speed is unverified.
- NLLB-200 is licensed CC-BY-NC and its card says it is "not released for production deployment", so it is avoided. (C: https://huggingface.co/facebook/nllb-200-distilled-600M)
- At the plan's cost of about $8.75 per million titles, $3 a month of Claude Batch polishes about 11,000 titles a day, roughly 5% of the feed (E).

**Language identification**
- Keep GDELT's own source-language code as the primary signal. GlotLID v4 (Apache-2.0, 2,060 labels) is the check; fastText lid.176 is CC-BY-SA. All tools struggle on short text: about 71 macro-F1 on tweets. (C: https://huggingface.co/cis-lmu/glotlid, https://arxiv.org/abs/2509.17768)

**Vector search in a small Postgres**
- pgvector 0.8.7 (2026-10-01) supports HNSW on halfvec and on bit vectors, with binary quantisation and re-ranking. (C: https://github.com/pgvector/pgvector)
- An HNSW index over 1M 128-dimension vectors measured 538 MB as halfvec and 298 MB as bits (C: https://jkatz05.com/post/postgres/pgvector-scalar-binary-quantization/). Extrapolated (E), 8 GB of RAM holds only 5–10M binary-quantised vectors.
- So: index story groups, not articles, in monthly partitions. pgvectorscale 0.9.1 (PostgreSQL licence, disk-based) is the fallback. (C: https://github.com/timescale/pgvectorscale)

**Story clustering**
- Nikolaidis et al. (Findings of EMNLP 2026) report that a nearest-neighbour graph with Leiden community detection beats HDBSCAN with every encoder and runs in seconds on a CPU. Using titles only costs 3–16 AMI points against full text. Their method is batch, not streaming. (C: https://aclanthology.org/2026.findings-emnlp.104.pdf)
- Evaluation datasets: UA-RU News (4,251 articles, 39 languages), Tokyo Olympics 2021 (10,940 articles, 9 languages), StreamBench (605 events). Licences for the first two are unverified. (https://arxiv.org/abs/2502.06648, https://arxiv.org/abs/2603.19250)

**Free GPU time for one-off jobs**
- Kaggle gives 30 GPU-hours a week (C: https://www.kaggle.com/docs/efficient-gpu-usage). A year of titles on e5-small is about 10 GPU-hours (E). GPU vectors differ slightly from CPU int8 vectors, so a backfill should run the pinned CPU model on Kaggle's free 4-core sessions, or the agreement should be measured first. Nothing in the running system depends on a GPU.

**Shortlist**

| Role | Pick | Licence | Speed | Quality |
|---|---|---|---|---|
| Embedding, whole feed | `intfloat/multilingual-e5-small` (384-d) | MIT | about 200 titles/s on 4 vCPU (E) | STS22x 0.655; NTREX 0.836 |
| Embedding, challenger | `hotchpotch/bekko-embedding-v1-a8m` (2026-07, 384-d, truncatable) | MIT | 364 docs/s on a Ryzen 9 (V); single maintainer | STS22x 0.681; NTREX 0.869 |
| Embedding, second pass | `microsoft/harrier-oss-v1-270m` (640-d) | MIT | about 40 titles/s on 4 vCPU (E); no CPU measurement found | STS22x 0.720; NTREX 0.925 |
| Embedding, alternative | `Alibaba-NLP/gte-multilingual-base` | Apache-2.0 | no CPU measurement found | STS22x 0.699; best titles-only clustering in the EMNLP study |
| Translation, bulk | Mozilla Firefox Translations students (55 pairs) | MPL-2.0 | about 3.4k tokens/s per thread (C) | COMET22 median 0.861 (V) |
| Translation, gaps | OPUS-MT `tc-bible-big` families through CTranslate2 | Apache-2.0 | 696 tokens/s on 4 threads for base (C) | at or above NLLB-600M for most languages; weak on Japanese, Somali, Burmese |
| Translation, polish | Claude Haiku 5.5, Batch API, top stories only | API | batch turnaround | not benchmarked here (U) |
| Translation, rare languages | `tencent/Hy-MT2-1.8B`; `google/madlad400-3b-mt` | Apache-2.0 | CPU speed unverified | MADLAD-3B chrF 54.4 on Flores into English |

(Model cards: https://huggingface.co/intfloat/multilingual-e5-small, https://huggingface.co/hotchpotch/bekko-embedding-v1-a8m, https://huggingface.co/microsoft/harrier-oss-v1-270m, https://huggingface.co/Alibaba-NLP/gte-multilingual-base, https://huggingface.co/tencent/Hy-MT2-1.8B, https://huggingface.co/google/madlad400-3b-mt. Claude pricing: https://platform.claude.com/docs/en/about-claude/pricing)

---

## F. Checks made on 2026-11-12, before the five threads

These were read on 12 November 2026 while sizing a first, smaller budget. They are recorded here because the plan relies on them. Marks as in section B.

**Oracle Cloud Always Free**
- The Ampere A1 allowance is 1,500 OCPU-hours and 9,000 GB-hours a month, which is 2 OCPU and 12 GB of RAM running all month. (C: https://docs.oracle.com/en-us/iaas/Content/FreeTier/resourceref.htm)
- It was 4 OCPU and 24 GB until 15 June 2026, when it was cut without an announcement. (S: https://infoq.com/news/2026/07/oracle-cloud-free-tier-limits/)
- Also free: 200 GB of block storage, 20 GB of object storage and 10 TB of outbound data a month. (C: same Oracle page)
- Idle rule: an Always Free instance may be reclaimed when, over 7 days, its CPU use at the 95th percentile, its network use and, for A1, its memory use are all under 20%. (C: same Oracle page)
- Whether a pay-as-you-go account is exempt from that rule, and whether a card is needed to open an account, were not confirmed (U).
- Not checked: whether an A1 instance can actually be created in a given region (capacity), and whether object storage has a write-once or retention setting on the free allowance.

**BigQuery sandbox**
- It needs no billing account and gives 10 GB of storage and 1 TB of queries a month. (C: https://cloud.google.com/bigquery/docs/sandbox)
- Third parties report that sandbox tables expire after 60 days (S). The 29 October report `data-gdelt.md` records the same allowances as 1 TiB of queries and 10 GiB of storage, with no DML or streaming.
- Not checked: that a project with no billing account can never be charged, how a job's credential works in a sandbox project, and whether custom quotas or keyless access from GitHub Actions apply there.

**Backblaze B2**
- The first 10 GB of storage is free (C on 12 November; the page address was not recorded, so re-read it in Week 0). Whether Object Lock is available on the free allowance was not checked (U).

**Not relied on**
- GitHub's Student Developer Pack: the DigitalOcean credit appeared to have ended after 31 July 2026; Azure's $100 was still listed (S).
