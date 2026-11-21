# GlobaLens 3.0: working agreement for Claude Code
## Map
apps/{web,api,admin,worker,jobs,taste-proxy,vault,check} · packages/{ui,lens,shot,miniglobe,analyst,api-client(generated),gdelt,glcore,py-client}
db/{migrations,functions} · infra/live/{bootstrap,storage,edge,node-paid,node-free,observability,github,web} · infra/burst/ · deploy/ · evals/ · bench/ · lab/ · docs/ (plan: docs/3.0/master-plan.md)
## Commands
mise run dev | check (lint+types+unit) | test | e2e | eval:quick | bench:<name> | tofu:plan | burst:<scenario>
## Rules
- Plan first: restate the task, list files to touch and the tests you will write first, then code. One task = one PR, Conventional Commits.
- Done means checked: `mise run check` passes (the Stop hook blocks "done" up to 8 times in a row; CI enforces it), the task's tests and evals pass, and the PR says what was verified and how.
  Never report a result you did not run.
- New dependency or service => ADR in docs/adr (template docs/adr/0000-template.md). No ADR, no merge.
- Money: no new paid service, plan or recurring cost without an ADR and the owner's approval. Every LLM route has a governor line;
  never raise a cap in code. The total stays at or under $20 a month at every cap (§14).
- Production is reached only through CI. Never run `tofu apply`, `tofu destroy`, a deploy command or SSH to a node from a session
  (deny rules enforce it). Open the PR; the owner merges it. A promotion or a planned drill is also a PR, to deploy/prod.lock
  (primary:, drill:).
- Roles: every service starts behind the role guard. Nothing may start cloudflared, the API, the taste proxy, the admin app,
  light jobs or timers on a node that prod.lock does not name primary, or whose ledger epoch is not current.
- DEPTH KERNELS (apps/worker/src/worker/ledger/*.py, packages/lens/src/kernel/*, apps/worker/storystream/assign.py, apps/jobs/quant/quantifier.py):
  a change updates the kernel's property tests and its walkthrough note in the same PR and requests the owner's line-by-line review.
- Data: never store full article text, ledes or thumbnails. Every upstream dataset needs a prov/sources.yml entry.
  Attribute GDELT in UI, API and MCP. Open-data drops, attested bundles, gold sets and the Bench never contain titles or glosses.
- Untrusted text: only glcore.untrusted may place external text (titles, names) in a prompt; API/MCP return titles
  only as structured fields marked untrusted. Machine translations and any model's output, including output produced with a
  visitor's own key or endpoint, are untrusted text. Render all of it as React text nodes with lang + dir from the known language
  (<bdi> otherwise); never innerHTML; build Atom/SVG with an XML library.
- Keys: a visitor's API key exists only inside apps/vault. No code outside it may read, log, store or transmit one.
  The site loads no third-party script (CI checks); the one exception, Cloudflare's Turnstile bot check, loads only inside the
  isolated frame on check.<domain>.
- LLM calls only through glcore.llm (server) or packages/analyst (browser, taste proxy, evals): memoized where shared, governed;
  thinking explicitly disabled on bulk routes (Haiku: effort <= high); explicit effort; structured outputs (output_config.format);
  no prefill; refusals handled; no temperature/top_p/top_k (API 2026-10-21); never echo cited text into user turns;
  count tokens with the target model.
- Ledger writes commit only with the current lease_token; the publisher, whose rows carry none, names its pass number,
  which must be the newest. Order-dependent (tier-2) code runs only in the ordered consumer.
  Model work (translation, embedding, MiniCheck) is requested as enrichment jobs; tier 2 never calls a model inline.
- Both nodes: every image builds for amd64 and arm64; nothing may assume one architecture or that the free node is present.
- Migrations are expand/contract: no destructive DDL in the release whose code needs it.
- Numbers: never write a metric into docs/README unless it exists in metrics/ledger.jsonl. Label (research)/(illustrative).
- SQL lives in db/ (dbmate). The API reads through the api_ro role. Regenerate the TS client after an OpenAPI change.
- Budgets that fail CI: size-limit, axe 0 serious, zizmor 0 high, OpenAPI drift 0, palette + collision check, font coverage,
  the third-party-script check, the CSP header check, Lens benchmark under CPU throttling (the 16 ms target is checked on real
  devices per release).
- No code copied from AGPL/GPL projects (World Monitor included); adapted MIT/BSD snippets are recorded in NOTICE.
- Secrets never in code, logs or telemetry. No network calls in unit tests (fixtures in tests/fixtures/). Committed fixtures
  carry synthetic or public-domain titles only; the real fixture week and the evaluation dumps stay in the private fixtures bucket.
- Rebuild drills never cancel the paid node's order and never destroy the free node's instance (prevent_destroy): they
  reinstall or rebuild in place through CI, or rebuild on an hourly machine. Destroys target infra/burst only; never storage.
