# ADR-0009: Hypothesis for the ledger's property tests

Status: proposed · 2026-11-20 · Phase 1 (task 10) · Spine: none

## Context: the requirement or measurement that forces a decision (link the metric/ledger entry)

The fenced ledger is depth kernel #1, and its claim is about every interleaving of several
workers: files are processed at least once and their effects land exactly once, whatever the
workers do. A handful of written-out scenarios cannot cover that. The plan asks for "Hypothesis
property tests including paused-worker interleavings" (Phase 1 task 10), and the design note for
1,000 generated histories with kills, pauses past the lease and duplicate listings, plus one run
with the fence removed that must fail (`docs/design/p1.md` §7.7, §10).

The owner approved adding `hypothesis` with the task's plan on 20 November 2026. No metric is
involved, so there is no ledger entry.

## Prior: what you expect each option to measure, before measuring (bake-offs and triggers)

There was no bake-off: the plan had named the tool. No prior was written down before the work,
so none is claimed.

## Options considered: each with cost, risk, ops burden, and the trigger that would change the answer

| Option | Why, or why not |
|---|---|
| Hypothesis, with its rule-based state machine | **Chosen.** It generates sequences of steps, checks invariants after every step, and when a sequence fails it shrinks it. With the fence removed, the failing history it reports is seven steps long and can be read aloud; an unshrunk one can be sixty |
| A loop over `random.Random(seed)` written here | No new dependency, but no shrinking, and a failing history of sixty random steps is not something a reviewer can follow |
| Threads, real sleeps and real kills | Tests the real concurrency, but cannot place a pause at a chosen point, cannot move the clock, and fails differently on every run. The tests that are about two transactions at the same instant do use threads; the histories do not |
| A model checker (TLA+) | It checks a model of the protocol, not the code. The plan has it as supporting work in Phase 2; it adds to these tests and does not replace them |

Trigger to revisit: the chaos harness of Phase 2 (seeded mutants against running processes). It
may reuse the state machine or stand beside it.

## Decision: exactly one choice

Add `hypothesis==6.170.15` to the `dev` group of the root `pyproject.toml`, pinned exactly. It
was released on 2026-11-06, inside ADR-0001's cooldown. It brings one package,
`sortedcontainers` 2.4.0. Both are used by tests only and are never installed in an image.

Licences: Hypothesis is MPL-2.0 and sortedcontainers is Apache-2.0. Neither is distributed with
anything this repository ships.

How it is used (`apps/worker/tests/pg/test_histories.py`):

- A history is a sequence of rules: list a file, start a worker, let a worker take its next
  step, kill a worker, move the clock. The workers are generators (`worker.ledger.tier1.walk`),
  so the test decides who moves next. They run against the real PostgreSQL 18 of the SQL tests.
- The main run generates new histories every time it runs (1,000 of them). A failure prints the
  shortest failing history and a `reproduce_failure` line that replays it.
- The run with the fence removed uses `derandomize=True`, so it finds the same violation on
  every run.
- `database=None`: Hypothesis keeps no database of past failures. It still makes a
  `.hypothesis` folder at the repository root for its own caches, with a `.gitignore` inside it
  that hides the folder from git, so the root `.gitignore` did not have to change.

## Evidence: bench/eval/bake-off links; pre-registration; prior vs measured

Run on the owner's Mac (Apple M3 Pro) on 2026-11-20 UTC, with `mise run test:ledger`:

- The 1,000-history run passes with the kernel as written. The test asserts that the histories
  did contain what they are for: commits with a stale token (all rejected), kills, pauses past a
  lease, and duplicate listings.
- With the line `and lease_token = %(token)s` removed from the commit, the same histories fail
  on "succeeded with a token that is not the row's current token".
- pyright in strict mode reads Hypothesis with no stubs.

Not verified: the tests on Linux or amd64.

## Consequences: what gets easier/harder; rollback plan; what we will measure next

**Easier.** A change to the kernel is checked against a thousand interleavings nobody had to
think of, and a failure arrives as a short history.

**Harder.** The main run is random. A history that fails once may not be generated again, so a
failure must be copied from the output (the history and its `reproduce_failure` line) before
the run is repeated. The property test takes minutes against a real database, which is why it
runs under `mise run test` and never under `mise run check`.

**Rollback.** Remove `apps/worker/tests/pg/test_histories.py` and the pin. The other tests of
the ledger do not use Hypothesis.

**Next.** Task 5 runs the property test in CI. Phase 2 adds the chaos harness and the TLA+ model.
