# Phase 2 — End-to-End Project

The most important phase. This is where concepts become craft.

## Picking the project

**Rules:**
1. Must be a real problem **you** have, that you'd actually use the result of
2. Must have ground truth — you know what a good answer looks like
3. Must be small enough to ship a v1 in a week

**Anti-patterns:**
- Generic chatbots
- Tutorial benchmarks (Spider, etc.) you don't actually need
- "An agent that does everything"
- Anything where success is too subjective to measure

## The week-by-week plan

- **Day 1-3** — Get the happy path working. Ugly is fine. **No optimization.**
- **Day 4-7** — Run 30+ real cases, categorize failure modes
- **Week 2** — Build eval infrastructure (20-50 case set + scoring script)
- **Week 3-4** — Iterate on top-3 failure modes; **every change runs the eval**
- **Week 5+** — Cost / latency / reliability optimization

## Deliverables

- Working code in this directory
- `eval/` subdirectory with eval set + scoring script
- `REPORT.md` documenting:
  - Problem statement
  - Approach
  - Eval methodology
  - Baseline metric → final metric (with intermediate iterations)
  - Top 3 most impactful changes and why
  - What you'd do differently next time

## Status

📝 Not started — project to be selected.

Candidates being considered:
- Auto-organize arXiv papers + find connections to ongoing research
- H100 training-run monitor agent (failure diagnosis + auto-restart)
- Auto-bootstrap experiment scaffolding from materials-science papers
- (others TBD)
