# GlobaLens 3.0 planning docs

**Status: plan only. Nothing in this folder is implemented yet.** Written 28–29 October 2026.

GlobaLens 3.0 rebuilds the June 2025 hackathon prototype as a live 3D globe of the world's news. You turn the planet under the Lens and read the real headlines from that place, in their own languages, grouped into stories and updated every 15 minutes. Its signature, **Exposure**, measures each language's coverage of a crisis against how severe the crisis is, with error bars and a weekly report anyone can recompute.

## Start here

| Read | What it is |
|---|---|
| [master-plan.md](master-plan.md) | **The plan of record.** TL;DR, product, design system, architecture, stack decisions, data, AI/ML, platform, the ten phases (tasks, tests, definition of done, demo, cut line), the Bake-off Lab, metrics, cost, risks, launch, open questions, and appendices: sources, glossary, Week-0 checklist, and the playbook for building it with Claude Code. |
| [brief.md](brief.md) | The brief the research and planning worked from: what you asked for and the working assumptions. |
| [north-star.md](north-star.md) | The synthesized vision the plan builds on. |
| [decision-notes.md](decision-notes.md) | The final calls made on top of the North Star (two layers, naming, the pivot gate, the Bake-off Lab, VM sizing, phase structure). The master plan already includes them. |
| [visions/judging.md](visions/judging.md) | How the direction was chosen: five competing visions, three judges, the scores and each judge's "must avoid" list. |
| [research/digest.md](research/digest.md) | The research summary. The nine reports in [research/](research/) hold the versions, prices, measurements, gotchas and source links. |
| [v1-audit.md](v1-audit.md) | What the hackathon version actually contains. |

**Short on time?** Read the master plan's header and §0 (one screen), then §17 (the open questions, each with a default).

## How the plan was made

1. **Research:** nine reports (market and competitors, GDELT measured on real files, severity data sources, frontend and geo, backend and data, AI/ML, platform, design, careers). The measurement scripts are in [research/scripts/](research/scripts/); they read local sample files and make no network calls.
2. **Five competing visions** (experience, intelligence, systems, AI-native, contrarian), each scored by three independent judges. The contrarian "Underexposed" thesis won; the North Star grafts the strongest ideas from the other four onto it.
3. **A draft plan** written to a fixed template, then attacked by **six critics**: technical correctness, sequencing, cost and operations, hiring impact, completeness, and fit with your brief. They raised 11 critical and 85 major issues.
4. **A revision** fixed each issue or rejected it with a written reason (39 changes, 14 rejections), followed by a consistency audit.
5. **A closure check** re-tested every critical and major issue against the revised text, fact-checked the vendor, price and version claims it had added, and read the plan as a first-time reader. The fixes from that check were applied and the plan was audited again. Of the 96 issues, 49 were fully closed and 47 needed more work (43 only partly fixed, 4 undone by later edits). 13 of 48 checked vendor, price and version claims needed correcting; for example, Chrome's on-device Translator API turned out to be desktop-only, and DuckDB 2.0 LTS replaced 1.5. 106 fixes followed, and the final audit found the phase hours, dates, costs and cross-references consistent.

## Conventions

- *(research)*: a value measured or quoted during research. A committed `bench/` or `evals/` script re-measures it before it appears in a README, résumé or `/stats`.
- *(illustrative)*: a placeholder, such as an example readout.
- `[Brackets]` in résumé lines are filled only from the metrics ledger, once measured.
- Dates assume Week 0 runs 2–8 November 2026 and Phase 1 starts on 9 November 2026.
