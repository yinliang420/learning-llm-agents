# learning-llm-agents

A hands-on, multi-phase plan for learning to **build** production-grade LLM agents — not just use them.

**👉 Start here: [LEARNING_PLAN.md](LEARNING_PLAN.md)**

## What this is

A personal learning repo, deliberately public so the journey (including the wrong turns) is visible. The end goal is a materials-science AI scientist agent capable of multi-day autonomous research, but the engineering foundation generalizes to any LLM agent project.

## What you'll find here

| Path | What's in it |
|---|---|
| [LEARNING_PLAN.md](LEARNING_PLAN.md) | The 4-phase syllabus |
| [shared/llm.py](shared/llm.py) | Unified LLM client wrapper (DashScope / Qwen by default, OpenAI-compatible, swap any backend via env) |
| [smoke_test/](smoke_test/) | Setup verification scripts (hello / tool-use / caching) |
| [phase1_patterns/](phase1_patterns/) | 5 design patterns, one folder each |
| [phase2_project/](phase2_project/) | End-to-end project (TBD) |
| [reports/](reports/) | Session-by-session progress reports — the honest log |
| [notes/journal.md](notes/journal.md) | Daily journal |

## Setup

```bash
uv sync                                 # creates .venv and installs deps
cp .env.example .env                    # then fill in DASHSCOPE_API_KEY (or other)
uv run python smoke_test/01_hello.py    # verify
```

You'll need:
- Python 3.13+
- An API key for an OpenAI-compatible endpoint. Default: [DashScope (Aliyun Qwen)](https://dashscope.console.aliyun.com/). You can also point at official OpenAI, OpenRouter, vLLM, etc. by overriding `OPENAI_BASE_URL` — see `.env.example`.
- (Optional) A free [Langfuse](https://cloud.langfuse.com) account for tracing

## Conventions

- Every LLM call routes through `shared.llm.call()` — uniform tracing, cost, retries
- Every session writes a [report](reports/)
- **Eval before feature** — write the eval, then iterate

## License

[MIT](LICENSE)
