# ADR-0001: One monorepo, with pnpm + Turborepo, uv and mise

Status: proposed · 2026-11-15 · Phase 1 (task 4) · Spine: none

## Context: the requirement or measurement that forces a decision (link the metric/ledger entry)

GlobaLens 3.0 is written in two languages (TypeScript for the site and the client packages,
Python for the worker and the data packages) with SQL, OpenTofu and Compose beside them. The
master plan (§6, "Monorepo" row; §9, "Monorepo") already chose the shape: one repository, pnpm
and Turborepo for JavaScript, uv for Python, mise for tools and tasks, a devcontainer. Phase 1
task 4 builds the skeleton, and tasks 8 (`db`) and 9 (`packages/gdelt`) start from it.

The plan pins some versions (Python 3.13, OpenTofu 1.13) and leaves the rest open. This ADR
records the versions chosen, the layout rules later tasks build on, and the three places where
the skeleton departs from the plan's wording. No metric is involved, so there is no ledger entry.

## Prior: what you expect each option to measure, before measuring (bake-offs and triggers)

There was no bake-off: the plan had chosen the tools before this task. No prior was written
down before the skeleton was built, so none is claimed here.

## Options considered: each with cost, risk, ops burden, and the trigger that would change the answer

The plan's own rejected options stand (Nx, Bazel, Poetry; §6). The choices below were open.

**Versions.** Each is the newest release that was at least 7 days old on 2026-11-15, unless a
row says otherwise.

| Tool | Version | Where pinned | Why this one; what would change it |
|---|---|---|---|
| Node.js | 26.13.0 | `mise.toml`, `package.json` engines | Node 26 is the active LTS line. 26.13.1 exists, but the mise on the owner's Mac (2025.4.0) cannot check its signature: the release is signed with a key that mise version does not carry. 26.13.0 verifies. Move to the newest 26.x once mise is upgraded |
| pnpm | 12.18.0 | `mise.toml`, `package.json` packageManager | Current major. Installed through mise's npm backend (`npm:pnpm`), because mise 2025.4.0 does not recognise pnpm 12's release files |
| Turborepo | 2.11.10 | `package.json` | Current 2.x |
| TypeScript | 6.0.3 | `package.json` | typescript-eslint 8.72 accepts TypeScript `<6.1.0` only, so TypeScript 7 cannot be linted yet. Move to 7 when typescript-eslint supports it |
| ESLint / typescript-eslint | 10.14.0 / 8.72.1 | `package.json` | Current; the plan names eslint |
| Vitest | 5.1.0 | `package.json` | Current; the plan names vitest |
| pyright | 1.1.414 | `package.json` | Installed from npm, so pnpm's lockfile pins it. The PyPI wrapper downloads the same program at run time, unpinned |
| uv | 0.13.7 | `mise.toml`, `uv_build` range in each `pyproject.toml` | Current |
| Python | 3.13 | `requires-python` in each `pyproject.toml` | The plan's pin. uv installs it (see "Departures") |
| ruff / pytest | 0.17.4 / 9.2.0 | `pyproject.toml`, `uv.lock` | Current; the plan names both |
| OpenTofu | 1.13.9 | `mise.toml`; `~> 1.13.0` in each stack | The plan's pin |
| dbmate | 2.37.0 | `mise.toml` | The plan names dbmate; first used by task 8 |
| age | 1.3.2 | `mise.toml` | Needed by task 6 for the escrowed key |
| mise | 2025.4.0 or later | `min_version` in `mise.toml`; v2026.11.4 in the devcontainer | 2025.4.0 is what the owner's Mac has, and the only version the skeleton was run with |

**Dependency cooldown.** The plan asks for pnpm's `minimumReleaseAge` and a cooldown for PyPI
(§9, threat model). Options: pnpm's default of one day, or longer. Chosen: 7 days for both
(`minimumReleaseAge: 10080` in `pnpm-workspace.yaml`; `exclude-newer` in `pyproject.toml`,
moved forward only by a dependency pull request). A week costs nothing while the project has no
users. Trigger to shorten it: a security fix that cannot wait, taken as a one-off exception.

**Python package layout.** A `src/` layout for every Python member (`apps/worker/src/worker/`),
which is uv's default and needs no path configuration for pytest or pyright; or a flat layout
that matches the paths the plan's `CLAUDE.md` gives for the depth kernels
(`apps/worker/ledger/*.py`). Chosen: `src/`. See "Departures".

**How Turborepo sees Python.** Either a second task runner for Python, or a small
`package.json` in each Python member whose scripts call ruff, pyright and pytest. Chosen: the
`package.json`, so that one `turbo run` covers both languages and "affected only" works across
them.

## Decision: exactly one choice

One repository with:

- **A pnpm workspace** over `apps/*` and `packages/*` only. The v1 folders and `lab/` are never
  members. Turborepo runs `lint`, `typecheck` and `test` in every member.
- **A uv workspace** whose root (`pyproject.toml`, not a package) depends on every Python member,
  so `uv sync --locked` builds one environment (`.venv`) from one lockfile.
- **mise** for tool versions and for the task names the plan fixes:

  | Task | What it runs today |
  |---|---|
  | `mise run check` | `install`, then `turbo run lint typecheck test`: eslint and `tsc` for TypeScript; ruff, pyright (strict) and pytest for Python; vitest; the hook tests |
  | `mise run test` | `install`, then `turbo run test`. The same unit tests as `check` until a task adds integration tests |
  | `mise run dev` | `turbo run dev`. No app has a `dev` script yet |
  | `mise run e2e` | `turbo run e2e`. No package has one yet |
  | `mise run bench:<name>` | One task per script in `bench/`. `bench:smoke` is a placeholder |
  | `mise run tofu:plan` | `tofu init -backend=false` and `tofu plan` in every stack under `infra/live`. It never applies |
  | `mise run install` | `pnpm install --frozen-lockfile` and `uv sync --locked` |

- **Rules for later tasks.**
  - A TypeScript package extends `tsconfig.base.json` and is linted by the root
    `eslint.config.js`.
  - A Python member has a `pyproject.toml` (its real dependencies) and a `package.json` (its
    three scripts). A dependency between two Python members is written in both files: under
    `[tool.uv.sources]` for uv, and as `"workspace:*"` in `package.json` so Turborepo knows the
    order.
  - Repository-level Python (`.claude/hooks`, `bench/`) is checked by the root package's own
    `lint`, `typecheck` and `test` scripts.
- **Committed Claude Code settings** (`.claude/settings.json`), from Appendix D:
  - *Stop hook* (`.claude/hooks/stop_check.py`): runs `mise run check` when a session is about
    to finish, and blocks while it fails. It keeps its own count, per session, of failing checks
    in a row, and after 8 blocks it lets the session stop and tells the user the work is not
    verified. Claude Code has an eight-block cap of its own, but that count restarts whenever
    Claude calls a tool, so a session that keeps trying would never be released by it.
  - *Deny rules*, in two layers: `permissions.deny` patterns for the plain forms, and a
    PreToolUse hook (`.claude/hooks/deny_prod.py`) that reads the whole command, because a
    pattern such as `Bash(tofu apply *)` does not match `tofu -chdir=… apply`,
    `/opt/homebrew/bin/tofu apply` or `bash -c 'tofu apply'`. Both refuse `tofu apply`,
    `tofu destroy`, deploy commands and SSH.
  - Both hooks are plain Python run by `/usr/bin/python3`, with no dependency on the project's
    toolchain, so they work before anything is installed.

## Evidence: bench/eval/bake-off links; pre-registration; prior vs measured

Run on the owner's Mac (Apple M3 Pro) on 2026-11-15, from a clean checkout of the branch:

- `pnpm install --frozen-lockfile`, `uv sync --locked`, `mise run check` and `mise run test`
  pass.
- `mise run tofu:plan` reports "No changes" for all five stacks; `mise run bench:smoke` runs.
- The hook tests (`.claude/hooks/tests`) cover 51 commands that must be refused and 31 that
  must be allowed, and the Stop hook's three behaviours: it blocks on a failing check, passes
  on a clean one, and gives up after 8 blocks in a row. The same three were then run against
  the repository's real check, with a failing test planted and removed.
- In a fresh headless session (`claude -p`, Claude Code 2.1.283) in the clean checkout:
  `ssh -V` and `/usr/bin/ssh -V` were both refused although every Bash command was allowed;
  with a failing test planted, the Stop hook's message reached the model as "block 1 of 8";
  with a clean tree the session ended normally.

Not verified: the devcontainer (Docker was not running); any mise newer than 2025.4.0; the
give-up after 8 blocks inside a live session (it was run by invoking the hook directly); an
interactive session.

## Consequences: what gets easier/harder; rollback plan; what we will measure next

**Easier.** One command checks both languages, locally, in the Stop hook and in CI (task 5).
Tasks 8 and 9 add files to folders that already lint and test.

**Departures from the plan's wording, for the owner to confirm.**

1. *Python is installed by uv, not by mise.* The plan's setup list has mise install Python.
   mise 2025.4.0 installs Python 3.13.18 incorrectly on this Mac ("missing a `lib`
   directory"), and uv does it reliably. There is also no `.python-version` file: pyenv on the
   owner's Mac reads that file and then cannot start `python3` anywhere in the repository,
   which would break the hooks.
2. *The kernel paths in `CLAUDE.md`.* Appendix D's text names `apps/worker/ledger/*.py` and
   `apps/worker/storystream/assign.py`. Under the `src/` layout these become
   `apps/worker/src/worker/ledger/*.py`. `CLAUDE.md` is committed as the plan wrote it; the
   line is corrected in the pull request that creates the first kernel (task 10), or the worker
   is moved to a flat layout then.
3. *Every direct SSH command is refused, not only SSH to a node.* No node has an address yet.
   Git over SSH still works, because Git starts `ssh` itself.

**Harder.** The deny hook can refuse a harmless command that looks like a forbidden one (an
unquoted `echo tofu apply`). It is a guard against mistakes, not a security boundary: what
keeps production safe is that a session holds no production credentials.

**Turborepo's cache is shared between worktrees.** A run in a linked git worktree, which is
where each Claude Code session works, writes its cache to `.turbo/cache` in the main checkout,
not in the worktree (Turborepo's documented default when `cacheDir` is not set). That gives
cache hits across sessions, and `.gitignore` covers the folder. Setting `"cacheDir":
".turbo/cache"` in `turbo.json` would give each worktree its own cache instead.

**Rollback.** Deleting `.claude/settings.json` removes both hooks and the deny rules. The
workspaces are ordinary pnpm and uv projects and can be split without rewriting code.

**Next.** Upgrade mise on the owner's Mac, then move Node to the newest 26.x and, if wanted,
pnpm back to mise's own installer. Build the devcontainer once Docker is running. Task 5 gives
Renovate the same 7-day cooldown and makes `mise run check` the body of `ci-ok`.
