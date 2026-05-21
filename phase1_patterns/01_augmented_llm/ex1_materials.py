"""
Pattern 01 — Example 1: Materials Q&A
======================================

Augmented LLM: 模型 + 数据库查询工具。

重点：Schema 设计的三个决策
  1. description 写 WHEN，不写 HOW
  2. enum 约束有限枚举值
  3. 工具返回 structured JSON，不返回自然语言

运行: uv run python phase1_patterns/01_augmented_llm/ex1_materials.py
"""

from __future__ import annotations
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from shared.llm import call

# ── 数据库（生产里换成真实 DB 调用，agent 代码完全不变）─────────────────────

DB: dict = {
    "steel":     {"Young's modulus": (200, "GPa"), "density": (7850, "kg/m³"), "melting point": (1370, "°C"), "hardness": (130,  "HB")},
    "aluminium": {"Young's modulus": (69,  "GPa"), "density": (2700, "kg/m³"), "melting point": (660,  "°C"), "hardness": (25,   "HB")},
    "SiC":       {"Young's modulus": (410, "GPa"), "density": (3210, "kg/m³"), "melting point": (2730, "°C"), "hardness": (2500, "HV")},
    "copper":    {"Young's modulus": (110, "GPa"), "density": (8960, "kg/m³"), "melting point": (1085, "°C"), "hardness": (35,   "HB")},
    "titanium":  {"Young's modulus": (116, "GPa"), "density": (4500, "kg/m³"), "melting point": (1668, "°C"), "hardness": (70,   "HB")},
}

# ── 工具函数（纯 Python，模型看不见这里）──────────────────────────────────────

def lookup(material: str, property: str) -> dict:
    mat = next((k for k in DB if k.lower() == material.lower()), None)
    if not mat:
        return {"found": False, "error": f"'{material}' not in DB", "available": list(DB)}
    prop = next((k for k in DB[mat] if k.lower() == property.lower()), None)
    if not prop:
        return {"found": False, "error": f"'{property}' not found", "available": list(DB[mat])}
    v, u = DB[mat][prop]
    return {"found": True, "material": mat, "property": prop, "value": v, "unit": u}

def list_all() -> dict:
    return {"materials": list(DB), "properties": list(next(iter(DB.values())))}

# ── 工具 Schema（模型只能看到这里）──────────────────────────────────────────────
#
# 关键原则：
#   description = WHEN to call this tool（使用场景）
#   enum        = 限定合法值，阻止模型发明不存在的属性名
#   required    = 必填字段，防止模型漏传参数

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "lookup",
            "description": (
                "Query a specific property of a material from the database. "
                "Use when the user asks for a concrete value. "
                "Never guess — always call this tool for actual data."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "material": {
                        "type": "string",
                        "description": "Material name, e.g. 'steel', 'SiC', 'aluminium'",
                    },
                    "property": {
                        "type": "string",
                        "enum": ["Young's modulus", "density", "melting point", "hardness"],
                        "description": "Property to retrieve.",
                    },
                },
                "required": ["material", "property"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_all",
            "description": (
                "List all materials and properties available in the database. "
                "Use when the user asks what's available, or to check before a lookup."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]

DISPATCH = {"lookup": lookup, "list_all": list_all}

# ── Agent ─────────────────────────────────────────────────────────────────────

SYSTEM = (
    "You are a materials science assistant. "
    "Always use tools for property data — never recall from memory. "
    "Report values with units."
)

def run(question: str) -> str:
    messages = [{"role": "user", "content": question}]

    # Round 1 ─────────────────────────────────────────────────────────────────
    r1 = call(messages, system=SYSTEM, tools=TOOLS, max_tokens=512)
    print(f"  [R1] finish={r1.finish_reason}  {r1.summary()}")

    if r1.finish_reason != "tool_calls":
        return r1.text  # 直接回答，无需工具

    for tu in r1.tool_uses:
        print(f"      → {tu['name']}({tu['input']})")

    # 把模型的 tool_call 消息存入历史
    raw = r1.raw.choices[0].message
    messages.append({
        "role": "assistant",
        "content": raw.content,
        "tool_calls": [tc.model_dump() for tc in (raw.tool_calls or [])],
    })

    # 执行每个工具，结果写回 messages
    for tu in r1.tool_uses:
        if tu["name"] not in DISPATCH:
            result = {"error": f"unknown tool '{tu['name']}'"}
        else:
            result = DISPATCH[tu["name"]](**tu["input"])
        print(f"      ← {result}")
        messages.append({
            "role": "tool",
            "tool_call_id": tu["id"],
            "content": json.dumps(result, ensure_ascii=False),
        })

    # Round 2 ─────────────────────────────────────────────────────────────────
    r2 = call(messages, system=SYSTEM, max_tokens=512)
    print(f"  [R2] finish={r2.finish_reason}  {r2.summary()}")
    return r2.text


# ── 测试问题（覆盖三种情形）──────────────────────────────────────────────────

QUESTIONS = [
    # 正常单工具调用
    "钢的杨氏模量是多少？",
    # 并行双工具（模型自主决策）
    "SiC 和铝的密度分别是多少，谁更轻？",
    # 调 list_all（不同工具）
    "数据库里支持查哪些材料？",
    # 模型无需工具可直接回答（观察是否省去工具调用）
    "Young's modulus 的物理含义是什么？",
    # 数据库没有的材料（测试错误处理）
    "钨的熔点是多少？",
]

if __name__ == "__main__":
    for q in QUESTIONS:
        print(f"\n{'='*60}")
        print(f"Q: {q}")
        print(f"A: {run(q)}")
