"""Paper QA Agent（Stage 1）。

架构：Pattern 02 Tool-use Loop
  - 模型自己决定调哪些工具、调几次
  - 三个工具：list_papers / read_paper / search_in_paper
  - 长任务用 MAX_TURNS 兜底
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# 让 import shared.* 能用
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from shared.llm import call
from tools import DISPATCH


# ─────────────────────────────────────────────────────────────────────────────
# Tool Schemas（OpenAI 格式）
# ─────────────────────────────────────────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_papers",
            "description": (
                "List all available papers with basic metadata (id, page count, "
                "first-page preview). ALWAYS call this FIRST if you don't know "
                "what papers are available or which paper might be relevant to the question."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_paper",
            "description": (
                "Read pages from a specific paper. Returns text content. "
                "Default reads first 4 pages (usually contains title/abstract/intro). "
                "For more specific sections, call again with `pages` parameter. "
                "If text is truncated, call again with later page range."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "paper_id": {
                        "type": "string",
                        "description": "Paper id (filename stem, e.g. '10.3390_catal8080328'). Get from list_papers.",
                    },
                    "pages": {
                        "type": "string",
                        "description": (
                            "Page range. Examples: '1-3' (pages 1 to 3), "
                            "'5' (single page 5), '1,3,5' (multiple), '1-3,7' (mixed). "
                            "Omit to read default first 4 pages."
                        ),
                    },
                },
                "required": ["paper_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_in_paper",
            "description": (
                "Search a keyword inside a specific paper. Returns all matches with surrounding context. "
                "Use this when you need to find specific mentions (e.g. 'baseline', 'overpotential', 'Tafel slope') "
                "without reading the entire paper."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "paper_id": {
                        "type": "string",
                        "description": "Paper id (filename stem). Get from list_papers.",
                    },
                    "keyword": {
                        "type": "string",
                        "description": "Keyword to search (case-insensitive).",
                    },
                },
                "required": ["paper_id", "keyword"],
            },
        },
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# System Prompt
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM = """You are a scientific paper research assistant for the field of electrocatalysis.
You have access to a small collection of papers via tools.

WORKFLOW:
1. If you don't know what papers exist, call list_papers() FIRST.
2. Pick the most relevant paper(s) based on the question.
3. Read targeted pages with read_paper(), or use search_in_paper() for specific terms.
4. Synthesize an answer ONLY from what you read in the tools. NEVER make up facts.
5. When citing a fact, mention which paper (by id) and roughly where (page or section).

CONSTRAINTS:
- If a tool returns found=false, tell the user clearly and list available papers.
- If a question can't be answered from the available papers, say so explicitly.
- Keep answers concise and grounded in the source text."""


# ─────────────────────────────────────────────────────────────────────────────
# Agent Loop（Pattern 02）
# ─────────────────────────────────────────────────────────────────────────────

MAX_TURNS = 10  # 防死循环


def run(question: str, verbose: bool = True) -> str:
    """单次 agent 调用，返回最终文本答案。"""
    messages = [{"role": "user", "content": question}]
    turn = 0

    while turn < MAX_TURNS:
        turn += 1
        r = call(messages, system=SYSTEM, tools=TOOLS, max_tokens=1024)

        if verbose:
            print(f"  [Turn {turn}] finish={r.finish_reason}  {r.summary()}")

        # 模型说完成了
        if r.finish_reason == "stop":
            return r.text

        if r.finish_reason != "tool_calls":
            return f"[unexpected finish_reason: {r.finish_reason}]\n{r.text}"

        # 打印 tool calls 看决策
        for tu in r.tool_uses:
            args_preview = {k: (v[:60] + "...") if isinstance(v, str) and len(v) > 60 else v
                            for k, v in tu["input"].items()}
            if verbose:
                print(f"      → {tu['name']}({args_preview})")

        # 追加 assistant 消息（带 tool_calls）
        raw = r.raw.choices[0].message
        messages.append({
            "role": "assistant",
            "content": raw.content,
            "tool_calls": [tc.model_dump() for tc in (raw.tool_calls or [])],
        })

        # 执行工具 + 追加结果
        for tu in r.tool_uses:
            name = tu["name"]
            if name not in DISPATCH:
                result = {"error": f"Unknown tool: {name}"}
            else:
                try:
                    result = DISPATCH[name](**tu["input"])
                except Exception as e:
                    result = {"error": f"{type(e).__name__}: {e}"}

            if verbose:
                preview = json.dumps(result, ensure_ascii=False)[:150]
                print(f"      ← {preview}...")

            messages.append({
                "role": "tool",
                "tool_call_id": tu["id"],
                "content": json.dumps(result, ensure_ascii=False),
            })

    return "[MAX_TURNS reached, agent did not complete]"


# ─────────────────────────────────────────────────────────────────────────────
# Smoke test
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    question = "我们一共有几篇论文？它们的主题大致是什么方向？"
    print(f"Q: {question}\n")
    answer = run(question, verbose=True)
    print(f"\nA: {answer}")
