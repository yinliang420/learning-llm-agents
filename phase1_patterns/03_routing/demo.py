"""
Pattern 03: Routing
===================

核心思路：先分类，再用专门的 prompt/工具处理
用便宜的模型做路由决策，用合适的模型做实际工作

三条路由：
  lookup   → 需要查数据库的问题（"钢的密度是多少"）
  compute  → 需要计算的问题（"200 GPa 是多少 MPa"）
  general  → 概念性问题，直接回答（"什么是杨氏模量"）

踩坑预警（demo 里有意展示）：
  1. 路由错误：混合型问题分类到单一类别
  2. 上下文丢失：路由时的信息没有传给专家
"""

from __future__ import annotations
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from shared.llm import call

import math
DB = {
    "steel":     {"Young's modulus": (200, "GPa"), "density": (7850, "kg/m³"), "melting point": (1370, "°C"), "hardness": (130,  "HB")},
    "aluminium": {"Young's modulus": (69,  "GPa"), "density": (2700, "kg/m³"), "melting point": (660,  "°C"), "hardness": (25,   "HB")},
    "SiC":       {"Young's modulus": (410, "GPa"), "density": (3210, "kg/m³"), "melting point": (2730, "°C"), "hardness": (2500, "HV")},
    "copper":    {"Young's modulus": (110, "GPa"), "density": (8960, "kg/m³"), "melting point": (1085, "°C"), "hardness": (35,   "HB")},
    "titanium":  {"Young's modulus": (116, "GPa"), "density": (4500, "kg/m³"), "melting point": (1668, "°C"), "hardness": (70,   "HB")},
}
_MATH = {k: v for k, v in math.__dict__.items() if not k.startswith("_")}
_MATH.update({"abs": abs, "round": round})

def lookup(material, property):
    mat = next((k for k in DB if k.lower() == material.lower()), None)
    if not mat: return {"found": False, "error": f"'{material}' not in DB"}
    prop = next((k for k in DB[mat] if k.lower() == property.lower()), None)
    if not prop: return {"found": False, "error": f"'{property}' not found"}
    v, u = DB[mat][prop]
    return {"found": True, "material": mat, "property": prop, "value": v, "unit": u}

def calculate(expression):
    try:
        return {"ok": True, "result": float(eval(expression, {"__builtins__": {}}, _MATH))}
    except Exception as e:
        return {"ok": False, "error": str(e)}

# ── Step 1: Router ────────────────────────────────────────────────────────────

ROUTER_SYSTEM = """Classify the user's question into exactly one category:
- lookup   : needs specific material property values from a database
- compute  : needs arithmetic/formula calculation (values are given in the question)
- general  : conceptual question, answerable from knowledge

Reply with ONLY one word: lookup, compute, or general"""

def route(question: str) -> str:
    r = call([{"role": "user", "content": question}], system=ROUTER_SYSTEM, max_tokens=10)
    label = r.text.strip().lower()
    if label not in ("lookup", "compute", "general"):
        label = "general"
    print(f"  [Router] → {label}")
    return label

# ── Step 2: Specialized handlers ─────────────────────────────────────────────

LOOKUP_TOOLS = [{"type": "function", "function": {
    "name": "lookup", "description": "Get a material property value.",
    "parameters": {"type": "object", "properties": {
        "material": {"type": "string"},
        "property": {"type": "string", "enum": ["Young's modulus", "density", "melting point", "hardness"]},
    }, "required": ["material", "property"]},
}}]

COMPUTE_TOOLS = [{"type": "function", "function": {
    "name": "calculate", "description": "Evaluate a math expression. Use for unit conversions and formulas.",
    "parameters": {"type": "object", "properties": {
        "expression": {"type": "string", "description": "Python math expression, e.g. '200 * 1000'"},
    }, "required": ["expression"]},
}}]

def handle_lookup(question: str) -> str:
    messages = [{"role": "user", "content": question}]
    r1 = call(messages, system="Answer using the lookup tool. Always report units.", tools=LOOKUP_TOOLS, max_tokens=512)
    if r1.finish_reason != "tool_calls": return r1.text
    raw = r1.raw.choices[0].message
    messages.append({"role": "assistant", "content": raw.content,
                     "tool_calls": [tc.model_dump() for tc in (raw.tool_calls or [])]})
    for tu in r1.tool_uses:
        result = lookup(**tu["input"])
        print(f"      → lookup({tu['input']}) ← {result}")
        messages.append({"role": "tool", "tool_call_id": tu["id"], "content": json.dumps(result)})
    return call(messages, system="Answer using the lookup tool.", max_tokens=512).text

def handle_compute(question: str) -> str:
    messages = [{"role": "user", "content": question}]
    r1 = call(messages, system="Use the calculate tool for precise results.", tools=COMPUTE_TOOLS, max_tokens=512)
    if r1.finish_reason != "tool_calls": return r1.text
    raw = r1.raw.choices[0].message
    messages.append({"role": "assistant", "content": raw.content,
                     "tool_calls": [tc.model_dump() for tc in (raw.tool_calls or [])]})
    for tu in r1.tool_uses:
        result = calculate(**tu["input"])
        print(f"      → calculate({tu['input']}) ← {result}")
        messages.append({"role": "tool", "tool_call_id": tu["id"], "content": json.dumps(result)})
    return call(messages, system="Use the calculate tool.", max_tokens=512).text

def handle_general(question: str) -> str:
    r = call([{"role": "user", "content": question}],
             system="You are a materials science expert. Answer concisely.", max_tokens=512)
    return r.text

HANDLERS = {"lookup": handle_lookup, "compute": handle_compute, "general": handle_general}

def run(question: str) -> str:
    label = route(question)
    return HANDLERS[label](question)

if __name__ == "__main__":
    questions = [
        "钢的杨氏模量是多少？",          # → lookup
        "200 GPa 等于多少 MPa？",        # → compute
        "什么是比刚度？",                # → general
        "SiC 比钢的杨氏模量高多少倍？",  # → 踩坑：混合型，路由可能选错
    ]
    for q in questions:
        print(f"\n{'='*60}\nQ: {q}")
        print(f"A: {run(q)}")
