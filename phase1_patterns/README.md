# Phase 1 — 5 Design Patterns

The 5 fundamental agent patterns. The goal is **not** to build polished products, but to develop **intuition**: which pattern fits which problem, and what each fails at.

> Reference: [Anthropic — Building Effective Agents](https://www.anthropic.com/research/building-effective-agents)

## Recommended order

Work through them sequentially — each builds on the previous one's concepts.

| # | Pattern | Why it matters | Failure modes to watch |
|---|---|---|---|
| [01](01_augmented_llm/) | Augmented LLM | The base unit — single call with tools/context | Schema misuse, context overflow |
| [02](02_tool_loop/) | Tool-use loop | Multi-turn agent making sequential decisions | Death loops, early stop, context bloat |
| [03](03_routing/) | Routing | Classify → dispatch (cost optimization) | Mis-classification, dropping context |
| [04](04_plan_execute/) | Plan-then-execute | Decouple planning from execution | Plan errors compounding, no replan |
| [05](05_reflection/) | Reflection / Evaluator-Optimizer | Self-critique and revise | Reflection that hurts (over-correction) |

## Per-pattern deliverables

For each pattern:
- **50-200 lines of code, no framework** (just `shared/llm.py`)
- Run on **20+ real cases**
- Write a `failure_analysis.md`: what failed, when, why
- Update `notes/journal.md` with what surprised you

## Done with Phase 1 when

You can answer, for any new agent task:
- Which pattern is the right starting point?
- What will likely fail first?
- How would you measure whether it's working?

## Anti-patterns at this phase

- Reaching for LangGraph / AutoGen / CrewAI before you've felt the pain that justifies them
- Skipping the failure analysis ("it kinda works")
- Picking toy tasks that don't expose any failure modes
