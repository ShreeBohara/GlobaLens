# GlobaLens 3.0 planning docs

**Status: plan only. Nothing in this folder is implemented yet.** Written 28–29 October 2026; revised on 13 November 2026 (plan revision 4) and on 14 November 2026 (plan revision 5).

**Revision 4 (13 November 2026)** rebuilt the plan around a new brief: at most $20 a month to run, $30–40 of one-off spending around launch, no rented GPUs, bring-your-own-key AI, and a build done by Claude Code. [rethink.md](rethink.md) is the approved proposal and [research/budget-rethink.md](research/budget-rethink.md) the research behind it. The master plan is the source of truth; where the proposal and the plan differ, the plan wins.

**Revision 5 (14 November 2026)** removed the calendar and recorded your answers to the open questions. The plan has an order and gates, not dates: a phase is built, checked and verified, and the next one starts after that; the one overlap is a soak that has to keep running for days (§10). §17 of the master plan holds the answers: the weekly report is published under your name; classrooms and NGO communications staff come first; the logistics defaults stand; billing is in the US with both servers in US West; the build runs on Claude Max 20x; the project folder moves to `~/Projects/GlobaLens`. One question stays open until the Phase 8 gate: whether to announce when the site opens or one phase later. The older documents in this folder (rethink.md, decision-notes.md, the visions and the research) still mention target dates and a "Week 0"; the master plan overrides them.

GlobaLens 3.0 rebuilds the June 2025 hackathon prototype as a live 3D globe of the world's news. You turn the planet under the Lens and read the real headlines from that place, in their own languages, grouped into stories and updated every 15 minutes. Its signature, **Exposure**, measures each language's coverage of a crisis against how severe the crisis is, with error bars and a weekly report anyone can recompute.

## Start here

| Read | What it is |
|---|---|
| [master-plan.md](master-plan.md) | **The plan of record.** TL;DR, product, design system, architecture, stack decisions, data, AI/ML, platform, the ten phases (tasks, tests, definition of done, demo, protected item), the Bake-off Lab, metrics, cost, risks, launch, open questions, and appendices: sources, glossary, the setup checklist, and the playbook for building it with Claude Code. |
| [rethink.md](rethink.md) | The approved proposal behind revision 4: the new brief, the budget, AI in four lanes, the two servers, and how the build runs when Claude writes the code. |
| [research/budget-rethink.md](research/budget-rethink.md) | The research for revision 4, with a confidence mark and a source on every fact: bring-your-own-key, free and hourly infrastructure, CPU-only models, in-browser compute, building with Claude Code. |
| [brief.md](brief.md) | The original brief the research and planning worked from: what you asked for and the working assumptions. Revision 4's brief is in rethink.md. |
| [north-star.md](north-star.md) | The synthesized vision the plan builds on. |
| [decision-notes.md](decision-notes.md) | The final calls made on top of the North Star (two layers, naming, the pivot gate, the Bake-off Lab, VM sizing, phase structure). The master plan already includes them. |
| [visions/judging.md](visions/judging.md) | How the direction was chosen: five competing visions, three judges, the scores and each judge's "must avoid" list. |
| [research/digest.md](research/digest.md) | The research summary. The nine reports in [research/](research/) hold the versions, prices, measurements, gotchas and source links. |
| [v1-audit.md](v1-audit.md) | What the hackathon version actually contains. |

**Short on time?** Read the master plan's header and §0 (one screen), then §17 (the decisions already made and the one question still open).

## How the plan was made

1. **Research:** nine reports (market and competitors, GDELT measured on real files, severity data sources, frontend and geo, backend and data, AI/ML, platform, design, careers). The measurement scripts are in [research/scripts/](research/scripts/); they read local sample files and make no network calls.
2. **Five competing visions** (experience, intelligence, systems, AI-native, contrarian), each scored by three independent judges. The contrarian "Underexposed" thesis won; the North Star grafts the strongest ideas from the other four onto it.
3. **A draft plan** written to a fixed template, then attacked by **six critics**: technical correctness, sequencing, cost and operations, hiring impact, completeness, and fit with your brief. They raised 11 critical and 85 major issues.
4. **A revision** fixed each issue or rejected it with a written reason (39 changes, 14 rejections), followed by a consistency audit.
5. **A closure check** re-tested every critical and major issue against the revised text, fact-checked the vendor, price and version claims it had added, and read the plan as a first-time reader. The fixes from that check were applied and the plan was audited again. Of the 96 issues, 49 were fully closed and 47 needed more work (43 only partly fixed, 4 undone by later edits). 13 of 48 checked vendor, price and version claims needed correcting; for example, Chrome's on-device Translator API turned out to be desktop-only, and DuckDB 2.0 LTS replaced 1.5. 106 fixes followed, and the final audit found the phase hours, dates, costs and cross-references consistent.
6. **The rethink (13 November 2026).** You changed the brief: about $20 a month to run, bring-your-own-key AI, no rented GPUs, and Claude Code doing the build. Five research threads checked what those constraints allow, and the proposal in [rethink.md](rethink.md) was approved.
7. **Revision 4.** A written specification fixed every number and rule first. Every section was then rewritten against it, six of them in parallel. Three independent audits read the whole result: a fact check of about 330 new claims against the research (32 findings), a numbers-and-names check (20 findings) and a design-coherence review (27 findings, two of them critical: a failover procedure that could not be carried out as written, and a model job that could stall story grouping). Every finding was decided and applied, about 600 edits in all. Two closure checks then re-read everything that had changed: they found no critical or major problem, and their 17 small corrections were applied too.
8. **Revision 5 (14 November 2026).** You ruled out a dated schedule and answered the open questions. The calendar table, the per-phase windows, the target and slow dates and the pace check were removed from the master plan, and "Week 0" became the setup checklist. Waits that come from outside, such as an approval that takes weeks or a soak that runs seven days, are still listed as waits (§10). Each edit was applied by a script that refused to write unless it found the exact text it expected, and the result was searched for leftover schedule wording. An independent reviewer then read the whole plan and found 22 further places, most of them sentences that quietly assumed a phase length; those were fixed as well.

## Conventions

- *(research)*: a value measured or quoted during research. A committed `bench/` or `evals/` script re-measures it before it appears in a README, résumé or `/stats`.
- *(illustrative)*: a placeholder, such as an example readout.
- `[Brackets]` in résumé lines are filled only from the metrics ledger, once measured.
- There is no calendar. Phases have an order and gates. A date in the plan is a fact (a release, a price check, a decision), never a target.
