# 02 — Tool-use Loop

Multi-turn agent: the model decides when to call tools and when to stop. The most common "agent" shape in real products.

## Goal

Build an agent that:
- Receives a multi-step task
- Calls tools iteratively (read → process → write → verify ...)
- Decides on its own when the task is complete
- Returns the final result

## Why it matters

This is the workhorse pattern for coding agents (Cursor, Claude Code, Devin), research assistants, and most "do something for me" agents.

## Failure modes to watch (the famous ones)

- **Death loops** — model keeps retrying the same tool with the same args
- **Early stop** — model declares "done" before it actually is
- **Context bloat** — accumulated tool outputs blow past context window
- **Tool order confusion** — picks the wrong tool first, then can't recover
- **Hallucinated tool calls** — invents tools that don't exist

## Implementation tips

- Cap loop iterations (e.g. `MAX_TURNS=15`)
- Truncate / summarize old tool outputs when nearing context limit
- Always return tool errors back to the model with actionable messages
- Log every turn with thought-action-observation, even if the model isn't doing explicit ReAct

## Self-eval

- Run **20+ real multi-step tasks**
- Measure: success rate, average turns, max turns, cases that hit MAX_TURNS
- Categorize failures by the modes above
- Write `failure_analysis.md`

## Status

📝 Not started
