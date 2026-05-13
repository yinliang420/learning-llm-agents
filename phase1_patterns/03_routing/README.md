# 03 — Routing

Classify the input first, then dispatch to a specialized prompt or tool chain. A simple cost / quality optimization: send simple queries to a cheap model, complex ones to an expensive model.

## Goal

Build a router that:
- Receives a user query
- Classifies it into one of N categories (e.g. simple Q&A / code generation / data analysis)
- Dispatches to the right specialized handler
- Returns a unified response shape

## Why it matters

Routing is how production systems achieve good cost / latency tradeoffs without sacrificing quality on the cases that need a strong model. Also the foundation of "agent of agents" architectures.

## Failure modes to watch

- **Mis-classification** — wrong route, wrong specialist, wrong answer
- **Lost context** — info from the routing step doesn't reach the specialist
- **Over-routing** — too many categories, classifier accuracy degrades
- **Under-routing** — categories so coarse the specialist still has to do all the work

## Implementation tips

- Start with 3-5 categories max
- Use a small/cheap model for routing (Haiku, qwen-turbo) — accuracy matters more than capability here
- Pass the original query *and* the routing decision to the specialist (don't make them re-parse)
- Log routing decisions separately for analysis

## Self-eval

- Run **20+ real queries** spanning all categories
- Measure: routing accuracy (vs. labeled ground truth), end-to-end accuracy, cost vs. always-strong-model baseline
- Write `failure_analysis.md`

## Status

📝 Not started
