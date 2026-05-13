# 05 — Reflection / Evaluator-Optimizer

Execute the task, then have the model (or a separate model) critique the result, then revise. The loop continues until quality is acceptable or budget runs out.

## Goal

Build an agent that:
- Produces an initial answer
- Self-critiques (or is critiqued by a separate evaluator)
- Revises based on critique
- Stops when quality is good enough or N rounds reached

## Why it matters

Reflection is one of the most powerful (and most over-used) techniques. Done right, it cleanly improves quality on tasks where the model can spot its own mistakes. Done wrong, it makes things worse.

## Failure modes to watch

- **Reflection that hurts** — model "improves" a correct answer into an incorrect one
- **Over-correction** — agent obsesses over minor issues, never finishes
- **Evaluator collusion** — when self-evaluating, model rubber-stamps its own work
- **Infinite revision** — no clear stopping criterion
- **Cost explosion** — N revisions × M reflection passes = expensive

## Implementation tips

- Use a **separate model** (or different prompt) for the evaluator vs the executor
- Force the evaluator to output a structured score + specific issues — not "looks good"
- Cap revision rounds (3-5 max)
- Compare against single-shot baseline; only ship reflection when it actually improves the metric

## Self-eval

- Run **20+ real cases** through both single-shot and with-reflection
- Measure: quality delta, cost delta, latency delta
- Identify case classes where reflection helps vs. hurts
- Write `failure_analysis.md`

## Status

📝 Not started
