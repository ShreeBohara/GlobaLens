# ADR-0011: CI on GitHub Actions, hardened, with Renovate, release-please and a Claude review

Status: proposed · 2026-11-20 · Phase 1 (task 5) · Spine: none

## Context: the requirement or measurement that forces a decision (link the metric/ledger entry)

Phase 1 task 5 builds the repository's CI (`docs/design/p1.md` §9; master plan §9, the CI/CD
row, the pipeline's steps 1 and 2, and the supply-chain row of the threat model). Until now
`main` had no workflow at all: the Stop hook's `mise run check` was the only check, and it gives
up after 8 blocks, so the plan makes the required `ci-ok` check the gate that cannot be passed.

The repository is public and, since 2026-11-20, owned by the free organisation `globalens`.
GitHub-hosted runners cost nothing for a public repository, the arm64 ones included, and an
organisation's repository can use a merge queue. The owner has deferred every payment step: no
domain, R2 not enabled, no Cloudflare token. So nothing here deploys or reads a bucket, and the
preview step of the pipeline waits for tasks 12 and 16.

The repository's rule is that a new dependency or service needs an ADR. This one covers every
piece the CI adds, none of them paid. No metric is involved, so there is no ledger entry.

## Prior: what you expect each option to measure, before measuring (bake-offs and triggers)

There was no bake-off, and no prior was written down before the first run, so none is claimed.

## Options considered: each with cost, risk, ops burden, and the trigger that would change the answer

| Need | Chosen | Rejected, and why | Trigger to revisit |
|---|---|---|---|
| Runners | GitHub-hosted `ubuntu-24.04` and `ubuntu-24.04-arm`, named exactly | Self-hosted runners: a machine to run and secure, and harden-runner is paid there. `-latest` labels: they move under us | Jobs outgrowing the hosted runners |
| Toolchain in CI | `jdx/mise-action`, at the devcontainer's mise (2026.11.4), installing exactly what `mise.toml` pins | `setup-node`, `setup-uv` and the rest one by one: a second list of versions to keep equal to `mise.toml` | mise-action no longer verifying its download |
| Egress control | StepSecurity's harden-runner, `egress-policy: block` with a per-job allow-list | Nothing: a compromised dependency could send the runner's token anywhere. Firewall rules written by hand in each job: what harden-runner does, without its reports | StepSecurity changing the free tier for public repositories |
| Workflow audit | zizmor, through `zizmorcore/zizmor-action`, which installs zizmor from a hash-locked list of wheels | `uvx zizmor`: pinned by version only. actionlint alone: it finds mistakes, not security weaknesses (it was run locally too) | — |
| Known vulnerabilities | OSV-Scanner 2.7.1 on `uv.lock` and `pnpm-lock.yaml`, installed by mise's aqua backend, which checks the release's published checksums | `google/osv-scanner-action`: a container image pinned by tag, not digest. Trivy: compromised in March 2026 (CVE-2026-33634; the plan rules it out). GitHub's alerts alone: they do not fail a pull request | OSV-Scanner dropping uv or pnpm lockfiles |
| Dependency updates | Renovate, the free GitHub App | Dependabot: no custom version patterns, so the PostgreSQL pin of the SQL tests, mise in CI and the CI tools would be missed | — |
| Releases | release-please, one release pull request kept open on `main` | Tags by hand: no changelog. semantic-release: it releases on every merge to `main`, not once a phase | Phases no longer released as `v3.0.0-pN` |
| Code scanning | CodeQL, advanced setup in `codeql.yml`: `actions`, `javascript-typescript`, `python`, built from source | Default setup (a repository setting): it cannot leave out `lab/` and `docs/`, and its configuration lives outside the repository | — |
| Pull request review | `anthropics/claude-code-action` on the owner's subscription (`CLAUDE_CODE_OAUTH_TOKEN`) and the workflow's own token | The Claude GitHub App's sign-in: another app to install. An API key: billed per token, against the $20 budget | The review costing more of the weekly limit than it is worth |

## Decision: exactly one choice

**Four workflows**, under `.github/workflows/`:

- `ci.yml`, on `pull_request` and `merge_group`. `ci-ok` needs every other job, runs even when one
  fails (`if: always()`), and fails if any of them failed or was cancelled: it is the one check
  a ruleset requires.

  | Job | What it runs |
  |---|---|
  | `check` | `mise run install` (`pnpm install --frozen-lockfile`, `uv sync --locked`), then `turbo run lint typecheck test --affected` against the pull request's base, or the merge group's |
  | `test` | `mise run test` on amd64 and arm64: every unit test (the GDELT contract tests among them) and the SQL tests against PostgreSQL 18 in a throwaway container (ADR-0007). The fixture-week check skips: the real week stays on the owner's machine |
  | `zizmor` | Every finding as an annotation; any high finding fails the job |
  | `osv-scanner` | Both lockfiles. A finding fails the job unless `.github/osv-scanner.toml` names it, with a reason and a date after which it fails again |
  | `ci-ok` | The gate |

- `codeql.yml`, on pull requests, pushes to `main` and weekly.
- `release-please.yml`, on pushes to `main`.
- `claude-review.yml`, on pull requests from this repository, not drafts and not bots. Without
  the secret it prints a notice and passes. It runs with `--max-turns 30` and
  `--max-budget-usd 5`, Claude Code's own telemetry off, and the repository's hooks off (they
  run `mise run check`, which that job does not install). The action keeps Claude's output out
  of the public log, so when a review fails the job prints one field of it: the text of
  Claude's final message, at most 500 characters, which says why. It is not part of `ci-ok`.

**Rules every workflow keeps** (`.github/tests/test_workflows.py` checks them under `mise run
check`; zizmor checks most of them again):

- `permissions: {}` at the top, and each job names what it needs. Only three jobs write:
  CodeQL (`security-events`), release-please (`contents`, `issues`, `pull-requests`) and the
  review (`pull-requests`).
- Every action pinned by its full commit SHA with a `# vX.Y.Z` comment, one pin per action.
  Each was the newest release at least 7 days old on 2026-11-20, and so are zizmor 1.32.0 and
  OSV-Scanner 2.7.1. mise is 2026.11.4, older than that: it is the devcontainer's, the one
  version ADR-0001 has run this `mise.toml` with on Linux.
- harden-runner is the first step of every job that runs an action, in block mode with an
  allow-list. Only `ci-ok`, which runs two shell lines, has none.
- No `pull_request_target` or `workflow_run` trigger; `actions/checkout` never keeps its token.
- A timeout on every job; runner images named exactly.

**What harden-runner sends to StepSecurity.** Read from the action's source (v2.22.4) and its
agent's (`step-security/agent` 0.18.1, the build installed on a public repository's
GitHub-hosted runner, its checksum pinned in the action):

- At the start of each job the action posts the repository's name, the run's ID, the job's name
  and a random correlation ID to `agent.api.stepsecurity.io`, from the runner's IP address, and
  receives a one-time key. The agent then fetches StepSecurity's list of blocked domains, its
  feature flags and GitHub's list of Actions domains from the same host.
- With telemetry on, the agent would also send `prod.app-api.stepsecurity.io` one record per DNS
  lookup (the domain, the address returned, the time, whether it was allowed) and one per
  outbound connection (address, port, domain, time, and the process that made it: its name, the
  SHA-256 of its executable, and its parent process). That is all the open part of the agent
  sends.
- The agent also links a library whose source is not public, `step-security/armour`, which a
  StepSecurity feature flag switches on. It watches the job's processes and some files, can stop
  a process, and is given the same API address, one-time key and telemetry setting. What it
  would report cannot be read from public source.
- At the end the action fetches a summary for the job's summary page from StepSecurity.

**So every job sets `disable-telemetry: true`** (allowed in block mode only). The agent then
sends no per-lookup or per-connection records, StepSecurity's hosts are left out of the job's
allowed endpoints, and the call at the start remains. The cost: no StepSecurity page of each
job's calls and no baseline to compare against. In block mode the allow-list already stops an
unexpected call, and the agent's own log, which harden-runner's post step prints at the end of
each job's log, names every domain it refused (`domain not allowed: …`), so the egress control
is the same. Turning telemetry on is one line per job.

**The allow-lists** were measured, not guessed: the jobs' own commands were run in an
`ubuntu:24.04` container, as a `runner` user, with every DNS lookup logged (see Evidence). The
`check` and `test` jobs allow GitHub, `nodejs.org`, npm's registry, PyPI, `releases.astral.sh`
(uv's Python builds), `mise-versions.jdx.dev` (mise's cache of GitHub release data and
attestations) and `tuf-repo-cdn.sigstore.dev` (Sigstore's trust root, for those attestations);
`test` adds Docker Hub, for the PostgreSQL image. Every job that runs mise-action allows
`tuf-repo-cdn.sigstore.dev` as well, `osv-scanner` included: mise-action checks the mise it
downloads against a Sigstore-signed packslip. The containers installed mise with `curl`, so they
could not show this; the first run on GitHub did (see Evidence), and a test now holds it. Five
more hosts are optional to mise: it
installs everything when they do not resolve. They are allowed all the same, so that a refused
domain in a job's log always means something new, and because harden-runner refuses a host
differently from that test (it answers the lookup with an address its firewall rejects, where
the test had no answer at all). They are `mise.jdx.dev` (its update check),
`endevco.github.io`, `api.osv.dev`, `api.npmjs.org` and `npm.jsr.io`, each a read-only public
service.

**Renovate** (`.github/renovate.json`): every update waits 7 days after its release, the same
as pnpm's `minimumReleaseAge` (ADR-0001), with explicit rules for npm, PyPI and the SHA-pinned
actions; an update still in its cooldown gets no branch. Updates arrive on Monday mornings
(UTC) in groups: the actions, the CI tools, npm minor and patch, PyPI minor and patch, and
mise, pnpm and Node.js each kept equal across the files that pin them. Majors come one at a
time. Nothing merges by itself. Custom managers track the pins Renovate cannot find alone: the
PostgreSQL image in `db/tests/pg/test_0001_ingest.py` (ADR-0007 asked for this), mise in
`ci.yml` and in the devcontainer, and the zizmor and OSV-Scanner versions. `lab/` is never
touched: the render spike is pre-registered.

**release-please** (`.github/release-please-config.json`): the whole repository is one
`simple` package, and `release-as` names the current phase, `3.0.0-p1`, so the release pull
request proposes `v3.0.0-p1` whatever the commit types say. Its changelog starts after
`v1-hackathon` (`bootstrap-sha`). Merging it at the phase's close tags the release; the next
phase's first pull request sets `release-as` to `3.0.0-p2`.

## Evidence: bench/eval/bake-off links; pre-registration; prior vs measured

Run on the owner's Mac (Apple M3 Pro, Docker Desktop 29.7.2) on 2026-11-20:

- `mise run check` passes in the task's worktree (21 of 21 tasks), with the new tests in
  `.github/tests` among the root package's tests. They were written before the workflows:
  with no workflow and no Renovate configuration, 19 of them failed and 7 had nothing to run on.
- The tests can fail: 19 deliberate breaks, applied one at a time to a copy (an action pinned
  by tag, `ci-ok` missing a job or not running `always()`, harden-runner in audit mode or with
  telemetry on, a checkout keeping its token, a write permission added, `pull_request_target`, a secret in a
  script, the review unguarded, mise versions apart, a 3-day npm cooldown, `lab/` not ignored,
  the PostgreSQL manager broken, an undated OSV exception, and others), were each caught.
- In `ubuntu:24.04` containers, as the jobs run it (mise 2026.11.4, `mise install`,
  `mise run install`, `turbo run lint typecheck test`), on `linux/arm64` and on `linux/amd64`
  (emulated): 21 of 21 tasks each, gdelt 200 passed and 1 skipped (the fixture-week check),
  glcore 42, root 173. The SQL tests were not run in a container (they need a Docker daemon of
  their own); ADR-0007 has them passing on the Mac and in the devcontainer.
- `.github/renovate.json` validates against Renovate's schema and
  `.github/release-please-config.json` against release-please's (check-jsonschema 0.39.0).
- `--affected` on commits in a scratch clone: this change, or any change to `ci.yml`, selects
  every package; a change in `packages/glcore` selects glcore and gdelt; a change in `docs/` or
  in `codeql.yml` selects the root package alone, whose tests include the workflow rules.
- zizmor 1.32.0, online: no finding with the regular persona (the one CI uses) or the pedantic
  one. The auditor persona reports two medium findings, `secrets-outside-env`, on the review's
  token: it is a repository secret, as the owner's setup asks, not an environment's.
- actionlint 1.7.12 with shellcheck 0.11.0: no error.
- OSV-Scanner 2.7.1 found one advisory: GHSA-g3hv-75wg-m249,
  medium, a denial of service through crafted glob patterns in minimatch 10.2.6. minimatch comes
  only with eslint and typescript-eslint, development tools that match the repository's own
  patterns. The fix is minimatch 11, which arrives with eslint 10.15.0 and typescript-eslint
  8.73.0; on 2026-11-20 both were still inside the 7-day cooldown. The exception in
  `.github/osv-scanner.toml` lasts until 2026-12-14. With it, the scan passes.
- The DNS lookups behind the allow-lists, from those containers; and `mise install` and
  `mise run install` both pass with the five optional hosts answering "no such domain".

On GitHub, pull request 14's first run (2026-11-20, commit `0463dce`): every job passed but
`osv-scanner`, which stopped in mise-action with "sigstore refused the bundle: error refreshing
TUF metadata"; the agent's log for that job shows `domain not allowed: tuf-repo-cdn.sigstore.dev`,
the only domain refused in any job of the run. The other jobs: `check` 21 of 21 tasks; `test` on
both architectures with the 39 SQL tests passing; zizmor no finding; CodeQL's three analyses
passing, with no alert; the review skipping with its notice. The next commit adds the host and
the test.

Not verified locally: anything that only GitHub can run. The pull request's own run is the
proof of `ci.yml`, CodeQL's analysis and upload, and the allow-lists on GitHub's runners.
release-please runs only on `main`, after the merge. The Claude review runs only once the
owner has added its secret; until then the job skips.

## Consequences: what gets easier/harder; rollback plan; what we will measure next

**Easier.** A pull request is checked the same way locally and on GitHub: CI calls `mise run`
tasks. Dependency updates arrive in reviewable weekly groups. Each phase's release is one merge.

**Harder, and what the owner does about it.**

- *A pull request opened by `release-please` starts no workflow* (GitHub does not start
  workflows from events made with a workflow's own token), so `ci-ok` never reports on it. At
  the phase's close, close and reopen the release pull request: a person's event starts the
  workflows. A GitHub App token would remove the step; it is not worth an app before P1 closes.
- *PyPI updates and `exclude-newer`.* uv refuses anything newer than the fixed date in
  `pyproject.toml`, and Renovate does not move it, so a PyPI update newer than that date fails
  its lockfile update until the date is moved in the same pull request. Follow-up: a rolling
  `exclude-newer = "7 days"` (uv 0.13 accepts it), which would match Renovate's cooldown.
- *Image updates from registries with no release dates* (GHCR, used by the devcontainer's
  Docker-in-Docker feature) wait forever under Renovate's default, which requires a date. They
  show on the Dependency Dashboard, where they can be started by hand.
- *Docker Hub re-pushes `postgres` tags often*, and Renovate dates a digest by the tag's last
  push, so the image's updates may wait more than 7 days.
- *A new host in a job's allow-list* is a change to a workflow, reviewed like any other.
- *The review's first real run is unverified.* Its allow-list comes from the action's source,
  not from a run.

**Waiting for task 12** (apps/web and its static export): size-limit, the third-party-script
check, and the header and script-policy check on the built export. They join `ci.yml` as jobs
that `ci-ok` needs.

**Rollback.** Delete a workflow file to remove it; delete `.github/renovate.json` or uninstall
the app to stop Renovate. Nothing outside `.github/` depends on them, except the root package's
scripts and `turbo.json`, which run the workflow tests.

**Next.** The owner's settings: the ruleset requiring `ci-ok`, the merge queue, Actions allowed
to create pull requests, the Renovate app, and the review's secret. Then the patch automerge
the plan asks for, once the ruleset makes it safe; and a release-please token, if closing and
reopening the release pull request becomes a chore.
