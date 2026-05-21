"""Stage 2 paper QA agent — 把 search_in_paper 换成 rag_search。

工具变化：
  list_papers         (沿用 Stage 1) — 看目录
  read_paper          (沿用 Stage 1) — 读全文 fallback
  rag_search          (新) — 语义检索（替代 search_in_paper）

预期改进（要用 eval 验证）：
  - 跨论文查询：1 次 rag_search 拿到所有相关 chunk，不用 N 次 search_in_paper
  - 语义匹配：用自然语言查询不用想精确关键词
  - 成本/延迟：大幅下降，特别是 hard cross-paper case
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# 让 import shared.* 能用
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
# 让 import tools (stage1) 能用
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.llm import call
from tools import list_papers, read_paper             # 沿用 Stage 1 的两个工具
from stage2.retriever import rag_search               # Stage 2 新工具


# ─────────────────────────────────────────────────────────────────────────────
# Tool Schemas
# ─────────────────────────────────────────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_papers",
            "description": (
                "List all available papers with basic metadata. "
                "Use FIRST if you don't know what papers exist."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rag_search",
            "description": (
                "Semantic search across the indexed papers using natural language. "
                "PREFER this over reading full papers — it returns the top-K most "
                "relevant chunks with paper_id and page number. "
                "For cross-paper questions, leave paper_ids=null to search all. "
                "For single-paper deep-dive, set paper_ids=['that_one']."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Natural-language query. Examples: 'OER overpotential value in mV', "
                            "'synthesis method using hydrothermal', 'Tafel slope'."
                        ),
                    },
                    "paper_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Optional: restrict search to these paper_ids. "
                            "Omit to search across all indexed papers."
                        ),
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "How many top chunks to return (default 5).",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_paper",
            "description": (
                "Read specific pages of a paper. Use ONLY if rag_search results "
                "are insufficient and you need broader context from a specific section."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "paper_id": {"type": "string"},
                    "pages": {
                        "type": "string",
                        "description": "Page range like '1-3' or '5' or '1,3,5'.",
                    },
                },
                "required": ["paper_id"],
            },
        },
    },
]


DISPATCH = {
    "list_papers": list_papers,
    "read_paper": read_paper,
    "rag_search": rag_search,
}


# ─────────────────────────────────────────────────────────────────────────────
# System Prompt（v2 efficiency rules 沿用 + 加 RAG 指引）
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM = """You are a scientific paper research assistant for the field of electrocatalysis.
You have access to a small collection of papers via tools.

CRITICAL — paper_id format:
  paper_ids are the FULL filename stems (without .pdf), NOT short names.
  ✅ Correct: "10.1002_cssc.201901439", "10.1016_j.ijhydene.2020.03.192", "10.3390_catal8080328"
  ❌ Wrong:  "cssc", "ijhydene", "catal8080328"
  If you're not sure of the exact id, call list_papers() FIRST.

WORKFLOW:
1. If you don't know what papers exist, call list_papers() FIRST to get exact paper_ids.
2. For factual / data / comparison queries, use rag_search() — semantic retrieval over chunks.
3. Only call read_paper() if rag_search is genuinely insufficient (e.g. need full section context).
4. Synthesize an answer ONLY from what the tools returned. NEVER make up facts.
5. When citing a fact, mention paper_id and page number from rag_search results.

EFFICIENCY GUIDELINES (HARD RULES — violating wastes tokens):
- TRUST the first rag_search result. If it returns ≥5 chunks with similarity > 0.3,
  USE THEM. Do NOT call rag_search again with rephrased queries hoping for "better" results.
- For cross-paper comparison, ONE rag_search with paper_ids=null usually gets you
  chunks from all relevant papers. Don't search each paper individually.
- For out-of-scope questions, use list_papers ONCE and judge from previews.
  Don't search exhaustively.
- For metadata (count / longest / author), list_papers is enough.
- Maximum recommended tool calls: 3 for simple, 5 for complex. Beyond that, summarize what
  you have and report any gaps explicitly.

CONSTRAINTS:
- If rag_search returns low-similarity matches (< 0.3), say so explicitly.
- If a question can't be answered from available data, say so — DO NOT keep searching."""


MAX_TURNS = 10


def run(question: str, verbose: bool = True) -> str:
    """Stage 2 agent loop（结构同 Stage 1，只是工具集不同）。"""
    messages = [{"role": "user", "content": question}]
    turn = 0

    while turn < MAX_TURNS:
        turn += 1
        r = call(messages, system=SYSTEM, tools=TOOLS, max_tokens=1024)

        if verbose:
            print(f"  [Turn {turn}] finish={r.finish_reason}  {r.summary()}")

        if r.finish_reason == "stop":
            return r.text

        if r.finish_reason != "tool_calls":
            return f"[unexpected finish_reason: {r.finish_reason}]\n{r.text}"

        for tu in r.tool_uses:
            args_preview = {k: (str(v)[:80] + "...") if isinstance(v, (str, list)) and len(str(v)) > 80 else v
                            for k, v in tu["input"].items()}
            if verbose:
                print(f"      → {tu['name']}({args_preview})")

        raw = r.raw.choices[0].message
        messages.append({
            "role": "assistant",
            "content": raw.content,
            "tool_calls": [tc.model_dump() for tc in (raw.tool_calls or [])],
        })

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

    return "[MAX_TURNS reached]"


if __name__ == "__main__":
    # 用 Stage 1 那个最贵的 hard case 来对比
    q = ("对比三篇 NiFe 论文（cssc / ijhydene / catal8080328）里报告的 OER overpotential 数据，"
         "哪一篇报告的 OER overpotential 数值最小？给出每篇的具体数值（mV）。")
    print(f"Q: {q}\n")
    print(f"A: {run(q, verbose=True)}")
