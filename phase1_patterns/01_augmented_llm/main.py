"""
Pattern 01: Augmented LLM
=========================

Single LLM call + at most ONE round of tool calls. No loop.

Full message flow:
  [user question]
      ↓
  model → finish_reason="tool_calls"  (wants data)
      ↓
  you execute the tools
      ↓
  model → finish_reason="stop"        (has data, answers)

This pattern covers ~50% of real production agents.
The trick is in the schema design and the messages format between rounds.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from shared.llm import call
from tools import lookup_material_property, list_materials

# ─────────────────────────────────────────────────────────────────────────────
# Tool Schemas
#
# The model never sees your Python code. It ONLY sees these strings.
# Every word is load-bearing.
#
# Key writing rule:
#   "description" should answer WHEN to use this tool, not HOW.
#   The model already knows HOW (it read your parameters schema).
# ─────────────────────────────────────────────────────────────────────────────

TOOL_LOOKUP = {
    "type": "function",
    "function": {
        "name": "lookup_material_property",
        "description": (
            "Look up a specific physical or mechanical property of a material "
            "from the database. Use when the user asks for a concrete value "
            "(e.g. Young's modulus, density, melting point, hardness). "
            "Do NOT guess values — always use this tool to retrieve real data."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "material": {
                    "type": "string",
                    "description": "Material name. e.g. 'steel', 'aluminium', 'SiC', 'copper', 'titanium'",
                },
                "property": {
                    "type": "string",
                    # Enumerating valid values stops the model from inventing
                    # property names like "tensile strength" (not in our DB)
                    "enum": ["Young's modulus", "density", "melting point", "hardness"],
                    "description": "The property to retrieve.",
                },
            },
            "required": ["material", "property"],
        },
    },
}

TOOL_LIST = {
    "type": "function",
    "function": {
        "name": "list_materials",
        "description": (
            "List all materials available in the database. "
            "Use this when the user asks what materials are supported, "
            "or to check if a material exists before querying its properties."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
}

TOOLS = [TOOL_LOOKUP, TOOL_LIST]

# ─────────────────────────────────────────────────────────────────────────────
# Tool Dispatcher
#
# You are the bridge between the model's JSON output and real Python functions.
# ─────────────────────────────────────────────────────────────────────────────

def execute_tool(name: str, args: dict) -> dict:
    match name:
        case "lookup_material_property":
            return lookup_material_property(**args)
        case "list_materials":
            return list_materials()
        case _:
            # Model hallucinated a tool name — handle gracefully
            return {"error": f"Unknown tool '{name}'. Available: lookup_material_property, list_materials"}


# ─────────────────────────────────────────────────────────────────────────────
# The Agent
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM = (
    "You are a materials science assistant with access to a property database. "
    "When the user asks for a material property value, always use the lookup tool — "
    "never guess or recall from training data. "
    "Report values with their units. Be concise."
)


def run_agent(question: str, verbose: bool = True) -> str:
    messages = [{"role": "user", "content": question}]

    # ── Round 1: model decides what to do ────────────────────────────────────
    r1 = call(messages, system=SYSTEM, tools=TOOLS, max_tokens=512)

    if verbose:
        print(f"\n[Round 1] finish_reason={r1.finish_reason!r}  {r1.summary()}")

    # Model answered without needing any tool
    if r1.finish_reason != "tool_calls":
        return r1.text

    # Model wants to call tools — print what it decided
    if verbose:
        for tu in r1.tool_uses:
            print(f"  → {tu['name']}({json.dumps(tu['input'], ensure_ascii=False)})")

    # ── Append the assistant's tool-call turn to messages ────────────────────
    # Why: the API requires the full tool_calls object to match against results.
    raw_msg = r1.raw.choices[0].message
    messages.append({
        "role": "assistant",
        "content": raw_msg.content,   # usually None when calling tools
        "tool_calls": [tc.model_dump() for tc in (raw_msg.tool_calls or [])],
    })

    # ── Execute each tool, append results ────────────────────────────────────
    for tu in r1.tool_uses:
        result = execute_tool(tu["name"], tu["input"])
        if verbose:
            print(f"  ← {result}")
        messages.append({
            "role": "tool",
            "tool_call_id": tu["id"],
            # Return structured JSON — model extracts values more reliably
            # than from prose strings like "The Young's modulus is 200 GPa."
            "content": json.dumps(result, ensure_ascii=False),
        })

    # ── Round 2: model now has real data, gives final answer ─────────────────
    r2 = call(messages, system=SYSTEM, max_tokens=512)

    if verbose:
        print(f"[Round 2] finish_reason={r2.finish_reason!r}  {r2.summary()}")

    return r2.text


# ─────────────────────────────────────────────────────────────────────────────
# Run
# ─────────────────────────────────────────────────────────────────────────────

QUESTIONS = [
    "钢的杨氏模量是多少？",
    "SiC 和铝，谁的硬度更高？",
    "你的数据库里有哪些材料可以查？",
    "帮我比较钛和铝的密度。",
]

if __name__ == "__main__":
    for q in QUESTIONS:
        print(f"\n{'='*60}")
        print(f"Q: {q}")
        answer = run_agent(q, verbose=True)
        print(f"\nA: {answer}")
