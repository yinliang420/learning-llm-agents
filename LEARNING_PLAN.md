# Learning LLM Agents — A Hands-On Plan

> A 4-phase, project-driven plan to learn how to **actually build** production-grade LLM agents — not just use them.

## Why this repo

Most "learn AI Agents in N days" tutorials get you to a working demo, then leave you with no idea why your real project is failing. This is the opposite — a deliberately slow path that prioritizes:

- **Understanding > frameworks** (you'll write a 50-line agent from scratch before touching LangGraph)
- **Evaluation > features** (the eval set comes before the next feature)
- **Reading rollouts > reading metrics** (looking at what the model actually did)
- **Cost-awareness from Day 1** (not bolted on later)
- **One real project >> ten demos** (Phase 2 is where most of the learning happens)

The end goal *for me* is a materials-science AI scientist that can autonomously run multi-day research workflows. The engineering generalizes.

## 4 Phases at a glance

| Phase | Theme | Duration | Output |
|---|---|---|---|
| **0** | Setup | 2-3 days | Unified LLM client, observability, smoke tests |
| **1** | 5 design patterns | 1-2 weeks | 5 minimal agents (50-200 LOC each) + failure analyses |
| **2** | End-to-end project | 4-8 weeks | Real-problem agent with eval metrics, baseline → optimized |
| **3** | Engineering depth | rolling | Tool design, memory, observability, cost/reliability mastery |
| **4** | Advanced (optional) | as needed | MCP, multi-agent, sandboxing, fine-tuning |

---

## Phase 0 — Setup

**Goals**
- Build a unified LLM client wrapper (`shared/llm.py`) that all future agent code routes through
- Wire observability (Langfuse) for trace, token usage, cost
- Verify the API stack end-to-end with smoke tests

**Deliverables**
- `shared/llm.py` — `call()` returning a `CallResult` (text, tool_uses, usage, cost, finish_reason)
- `smoke_test/` — 3 scripts: hello / tool-use / caching
- First entry in `notes/journal.md`

**Self-eval — Phase 0 is done if you can answer:**
- Can you make a Claude / Qwen / Gemini call from one line via the wrapper?
- Can you see token + cost of every call?
- Can you switch model with one env var?
- Have you read your own first trace in the observability tool?

**Resources**
- [Anthropic API docs](https://docs.anthropic.com/)
- [DashScope OpenAI-compatible mode](https://help.aliyun.com/zh/model-studio/developer-reference/use-qwen-by-calling-api)
- [Langfuse docs](https://langfuse.com/docs)

---

## Phase 1 — 5 Design Patterns

**Goals**
- Build hands-on intuition for the 5 fundamental agent patterns
- Develop the "which pattern fits this problem" mental model
- Personally feel each pattern's failure modes

**The 5 patterns**

| # | Pattern | Description |
|---|---|---|
| 01 | Augmented LLM | Single call + retrieval/tools, no loop |
| 02 | Tool-use loop | Multi-turn, model decides when to stop |
| 03 | Routing | Classify → dispatch to specialized prompt/tool |
| 04 | Plan-then-execute | Generate plan, execute steps |
| 05 | Reflection / Evaluator-Optimizer | Execute, critique, improve |

**Per-pattern deliverables**
- 50-200 LOC, **no framework** (just `shared/llm.py`)
- 20+ real cases run, with logs
- A `failure_analysis.md` documenting what failed, when, why

**Self-eval**
- For any new agent task: can you predict which pattern fits, and which failure modes you'll see first?
- Can you cite specific cases where each failure mode actually occurred?

**Resources**
- [Anthropic — Building Effective Agents](https://www.anthropic.com/research/building-effective-agents)
- [OpenAI Cookbook — Agents](https://cookbook.openai.com/)

---

## Phase 2 — End-to-end Project

The most important phase. This is where concepts become craft.

**Goals**
- Pick a real problem **you actually need solved** (not a tutorial example)
- Build the smallest version that works
- Build evaluation infrastructure **before** adding features
- Iterate with metrics

**Why a real problem?**
- You have ground truth (you know what good looks like)
- You'll keep using it → discover real failure modes
- You'll be willing to optimize it
- Your portfolio / interview story is real, not contrived

**Candidate projects (for inspiration)**
- Auto-organize arXiv papers + find connections to your work
- Auto-review your commits / generate PR descriptions
- Monitor + auto-recover training runs on a GPU cluster
- Auto-bootstrap experiment scaffolding from papers

**Week-by-week**
- **Day 1-3**: Happy path working. Ugly is fine. **No optimization.**
- **Day 4-7**: Run 30+ real cases, categorize failure modes
- **Week 2**: Build eval infrastructure (20-50 case set + scoring script)
- **Week 3-4**: Iterate on top-3 failure modes; every change runs the eval
- **Week 5+**: Cost / latency / reliability optimization

**Deliverables**
- Working code in `phase2_project/`
- `phase2_project/eval/` with eval set + scoring script
- `phase2_project/REPORT.md`:
  - Problem statement
  - Approach
  - Eval methodology
  - Baseline → final metric
  - Top 3 changes and why
  - What you'd do differently

**Self-eval**
- What's your task completion rate? Tool call accuracy? Cost per task?
- Can you point to specific failure modes you fixed and the metric improvement?
- Can a stranger read your REPORT.md and understand what you built and why?

**Resources**
- [SWE-bench paper](https://arxiv.org/abs/2310.06770)
- [LLM-as-judge](https://arxiv.org/abs/2306.05685)

---

## Phase 3 — Engineering Depth (rolling)

Not a discrete phase — touched throughout Phase 2. Use this as a checklist.

**Tool design**
- Schema as documentation: `when-to-use` > `how-to-use`; enumerate values; structured output
- Tool granularity: not too coarse, not too fine
- Error returns that are actionable for the model

**Context engineering**
- System prompt as cache prefix (use prompt caching)
- Memory layers: session / persistent / shared knowledge
- Long-context handling: summarization, retrieval, windowing

**Observability**
- Every LLM call logged: input / output / tool calls / tokens / cost / latency
- Trace IDs spanning a full agent execution
- Failure clustering by error type / user intent / tool

**Cost & reliability**
- Prompt caching, model tiering (cheap model for routing, strong model for reasoning)
- Parallel tool calls, streaming, batch API
- Retry strategy, fallback model, output validation, idempotency

---

## Phase 4 — Advanced (only when needed)

Don't pre-emptively learn these. Touch them when your project actually demands it.

- **MCP (Model Context Protocol)** — when you need to plug into the wider tool ecosystem
- **Multi-agent** — only when single-agent truly cannot do the job (most real problems don't need this)
- **Sandboxing** — when the agent runs untrusted code (Docker / Firecracker / e2b)
- **Human-in-the-loop** — for high-stakes / long-running tasks
- **Fine-tuning** — after you've maxed out prompt / tool engineering

---

## Progress

See [reports/](reports/) for session-by-session progress and decisions.

**Current**: Phase 0 (setup, Langfuse integration pending).

---

## How to use this repo (for visitors)

This is a personal learning repo — not a framework to install. But you might find useful:

- The plan above as a learning template
- [`shared/llm.py`](shared/llm.py) as a starting point for your own LLM wrapper
- [`reports/`](reports/) for an honest log of what worked, what didn't, and what was harder than expected
- Each phase's `README.md` for goals and self-eval criteria

If you want to follow along, fork it and customize the phases for your own goals. Tickets / PRs welcome but I'll prioritize my own learning over feature requests.

---

## References & inspiration

- [Anthropic — Building Effective Agents](https://www.anthropic.com/research/building-effective-agents)
- [Anthropic — Effective Context Engineering](https://www.anthropic.com/research/effective-context-engineering)
- [OpenAI — Agents docs](https://platform.openai.com/docs/guides/agents)
- [LangGraph docs](https://langchain-ai.github.io/langgraph/)
- [SWE-agent / SWE-bench](https://www.swebench.com/)
