"""Unified OpenAI-compatible LLM client wrapper.

Targets DashScope (Aliyun Qwen) by default, but works with any OpenAI-compatible
endpoint by overriding OPENAI_BASE_URL: vLLM self-hosted, OpenRouter, OpenAI proper, etc.

Every LLM call in this project should go through `call()` so token usage,
cost, and (later) Langfuse traces are recorded uniformly.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# UNVERIFIED approximate USD per million tokens for DashScope Qwen models.
# These are rough conversions from CNY pricing — DO NOT trust the cost number
# in production. Verify against your real DashScope invoice and update before
# any cost-based decision.
# Pricing source: https://help.aliyun.com/zh/model-studio/billing
PRICING: dict[str, dict[str, float]] = {
    "qwen-max":          {"in": 2.40, "cache_in": 0.24, "out": 9.60},
    "qwen-plus":         {"in": 0.11, "cache_in": 0.011, "out": 0.29},
    "qwen-turbo":        {"in": 0.043, "cache_in": 0.0043, "out": 0.086},
    "qwen3-max":         {"in": 2.40, "cache_in": 0.24, "out": 9.60},
    "qwen3-plus":        {"in": 0.11, "cache_in": 0.011, "out": 0.29},
    "qwen3-turbo":       {"in": 0.043, "cache_in": 0.0043, "out": 0.086},
    "qwen3-coder-plus":  {"in": 0.43, "cache_in": 0.043, "out": 2.86},
    "qwen-3.6-plus":     {"in": 0.11, "cache_in": 0.011, "out": 0.29},  # UNVERIFIED, copy of plus tier
    "qwen3.6-plus":      {"in": 0.11, "cache_in": 0.011, "out": 0.29},  # alias spelling
}

DEFAULT_MODEL = os.getenv("LLM_MODEL", "qwen-plus")
DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

_client: OpenAI | None = None


def client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "No API key found. Set DASHSCOPE_API_KEY in .env "
                "(or OPENAI_API_KEY for non-DashScope endpoints)."
            )
        _client = OpenAI(
            api_key=api_key,
            base_url=os.getenv("OPENAI_BASE_URL") or DEFAULT_BASE_URL,
        )
    return _client


@dataclass
class CallResult:
    text: str
    raw: Any
    model: str
    finish_reason: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    cost_usd: float = 0.0
    tool_uses: list[dict] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"model={self.model} finish={self.finish_reason} "
            f"in={self.input_tokens} out={self.output_tokens} "
            f"cached={self.cached_tokens} cost=${self.cost_usd:.6f}"
        )


_warned_models: set[str] = set()


def _calc_cost(model: str, in_tok: int, out_tok: int, cached: int) -> float:
    p = PRICING.get(model)
    if not p:
        if model not in _warned_models:
            import sys
            print(
                f"[llm.py] WARNING: no pricing entry for model '{model}', "
                f"cost will be reported as $0. Add it to PRICING in shared/llm.py.",
                file=sys.stderr,
            )
            _warned_models.add(model)
        return 0.0
    return (
        (in_tok - cached) * p["in"]
        + cached * p["cache_in"]
        + out_tok * p["out"]
    ) / 1_000_000


def call(
    messages: list[dict],
    *,
    system: str | None = None,
    tools: list[dict] | None = None,
    model: str = DEFAULT_MODEL,
    max_tokens: int = 1024,
    **kwargs: Any,
) -> CallResult:
    """Single LLM call. Returns parsed result with usage and cost."""
    msgs = list(messages)
    if system is not None:
        msgs = [{"role": "system", "content": system}] + msgs

    req: dict[str, Any] = {
        "model": model,
        "messages": msgs,
        "max_tokens": max_tokens,
        **kwargs,
    }
    if tools:
        req["tools"] = tools

    resp = client().chat.completions.create(**req)

    choice = resp.choices[0]
    msg = choice.message
    text = msg.content or ""

    tool_uses: list[dict] = []
    for tc in (msg.tool_calls or []):
        try:
            args = json.loads(tc.function.arguments) if tc.function.arguments else {}
        except json.JSONDecodeError:
            args = {"_raw": tc.function.arguments}
        tool_uses.append({"id": tc.id, "name": tc.function.name, "input": args})

    u = resp.usage
    cached = 0
    details = getattr(u, "prompt_tokens_details", None)
    if details is not None:
        cached = getattr(details, "cached_tokens", 0) or 0

    return CallResult(
        text=text,
        raw=resp,
        model=model,
        finish_reason=choice.finish_reason,
        input_tokens=u.prompt_tokens,
        output_tokens=u.completion_tokens,
        cached_tokens=cached,
        cost_usd=_calc_cost(model, u.prompt_tokens, u.completion_tokens, cached),
        tool_uses=tool_uses,
    )
