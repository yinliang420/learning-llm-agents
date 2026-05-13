# 01 — Augmented LLM

A single LLM call augmented with retrieval and/or one tool call. **No loop.** The simplest "agent" pattern (debatably even an "agent" at all).

## Goal

Build an LLM call that:
- Takes a user question
- Optionally retrieves relevant context from a small knowledge base
- Optionally calls one tool
- Returns the answer

## Why it matters

Many "agents" in production are just this pattern, well-engineered. Don't underestimate it: a clean augmented LLM beats a sloppy multi-step agent every time.

## Failure modes to watch

- Tool schema not specific enough → model passes wrong args
- Returned context too long → exceeds context budget
- Returned context too short → model hallucinates anyway
- Model doesn't call the tool when it should (under-tool-use)

## Self-eval

- Run **20+ real questions**
- Categorize each result: ✅ correct / ⚠️ partial / ❌ wrong
- For each ❌, root-cause: model error / schema error / context error / data error
- Write `failure_analysis.md` summarizing patterns

## Status

📝 Not started
