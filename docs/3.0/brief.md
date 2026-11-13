# GlobaLens 3.0 — Planning brief

Written on 2026-10-28 at the start of planning. This is the brief the research and planning agents worked from; the plan's open questions (master-plan.md §17) confirm or revise its assumptions.

## What the user asked for (paraphrased faithfully)
- They built **GlobaLens** ~16 months ago (June 2025) at a hackathon with no time. They love the idea.
- They want a full **2.0 / 3.0 redesign from scratch**, covering *everything*: frontend, UI, data, tools,
  backend, database, architecture, libraries, every detail. Can add features, modify the idea, change the
  scope in any direction.
- Must become **one of the top projects on their resume** — "if the CEO of Google saw this, he'd want to hire
  this developer instantly." "Make it extra, extra crazy." Unique, creative, UI-heavy, fast, robust, scalable.
- Open to any tech: Next.js, Python, C++ (if required), Terraform, AI/ML, CI/CD, GitHub pipelines, etc.
- Current UI is "very bad". Wants more layers, more features, more complex capabilities.
- Deliverable of this session: **deep research + a 10-phase plan** taking the project from ~1.7k LOC to a
  30k–100k LOC system. No implementation yet.

## Working assumptions (made at the start of planning; to be confirmed)
- **Solo developer**, early career; will implement with heavy AI-coding assistance (Claude Code), phase by phase.
- **Budget-conscious**: target ≤ ~$50/month steady-state hosting (free tiers / credits OK; short bursts OK for
  demos). Previously used GCP (Cloud Run, Firebase Hosting, BigQuery) and MongoDB Atlas.
- **Timeline**: multi-month; every phase must end in something **shippable and demoable** (vertical slices),
  so the project is impressive even if the user stops after phase 4 or 6.
- **Target roles**: broad — SWE (full-stack/systems), AI/ML engineer, data engineer. "T-shaped": breadth across
  the stack plus genuine depth in 2–3 areas (e.g., streaming data/ML systems, geo-visualization, AI agents).
- Tech choices must be **justified by real requirements**, not resume buzzword soup. A senior engineer reading the
  repo should think "every piece earns its place."
- Keep the name **GlobaLens** and the tagline idea "See beyond the headlines" unless there's a compelling reason.
- Public GitHub repo + a live demo URL are expected.
