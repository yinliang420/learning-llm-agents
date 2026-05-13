# 04 — Plan-then-Execute

Generate a structured plan first, then execute the steps. Useful when the task has clear sub-steps that benefit from upfront thinking.

## Goal

Build an agent that:
- Receives a complex task
- Generates a plan (typically a list of steps with their tools)
- Executes each step
- Returns final aggregated result

## Why it matters

Decoupling planning from execution makes the agent's reasoning visible, debuggable, and modifiable. You can intervene mid-plan, parallelize steps, or replan when execution fails.

## Failure modes to watch

- **Plan errors compound** — bad first step poisons everything downstream
- **No replanning** — execution failure should trigger plan revision, not retry
- **Plans too granular** — 30-step plans where 3 steps would do
- **Plans too vague** — "step 1: figure it out"
- **Plan-execution drift** — execution diverges from plan but the plan isn't updated

## Implementation tips

- Force structured plan output (Pydantic schema) so each step is parseable
- Execute steps with their own bounded loop (don't recurse)
- After each step, ask: "is the plan still valid? do we need to replan?"
- Cap total steps to prevent runaway

## Self-eval

- Run **20+ real complex tasks**
- Measure: plan quality (subjective rubric), execution success rate, replan frequency, average steps
- Compare against pure tool-loop on the same tasks
- Write `failure_analysis.md`

## Status

📝 Not started
