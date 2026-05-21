"""
Pattern 02: Tool-use Loop
=========================

与 Pattern 01 的本质区别：
  01 = 单轮工具调用，模型拿到数据就结束
  02 = 循环调用，模型自己决定"还需要什么"直到完成

典型场景：下一步需要什么工具，取决于上一步的结果
  → 这种条件分支是 Pattern 01 做不到的

Demo 任务：筛选材料
  "密度 < 4000 kg/m³ 且 杨氏模量 > 100 GPa 的有哪些材料？"
  Step 1: list_all()                    ← 不知道有哪些材料，先查
  Step 2: lookup 每个材料的密度          ← 结果决定哪些继续查
  Step 3: 对通过的材料查杨氏模量        ← 依赖 Step 2 的结果

这三步串行依赖，Pattern 01 无法处理。
"""

from __future__ import annotations
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from shared.llm import call

DB = {
    "steel":     {"Young's modulus": (200, "GPa"), "density": (7850, "kg/m³"), "melting point": (1370, "°C"), "hardness": (130,  "HB")},
    "aluminium": {"Young's modulus": (69,  "GPa"), "density": (2700, "kg/m³"), "melting point": (660,  "°C"), "hardness": (25,   "HB")},
    "SiC":       {"Young's modulus": (410, "GPa"), "density": (3210, "kg/m³"), "melting point": (2730, "°C"), "hardness": (2500, "HV")},
    "copper":    {"Young's modulus": (110, "GPa"), "density": (8960, "kg/m³"), "melting point": (1085, "°C"), "hardness": (35,   "HB")},
    "titanium":  {"Young's modulus": (116, "GPa"), "density": (4500, "kg/m³"), "melting point": (1668, "°C"), "hardness": (70,   "HB")},
}

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

TOOLS = [
    {"type": "function", "function": {
        "name": "lookup",
        "description": "Query a specific property of a material. Use when you need a concrete value.",
        "parameters": {"type": "object",
            "properties": {
                "material": {"type": "string"},
                "property": {"type": "string", "enum": ["Young's modulus", "density", "melting point", "hardness"]},
            }, "required": ["material", "property"]},
    }},
    {"type": "function", "function": {
        "name": "list_all",
        "description": "List all available materials. Use this first if you don't know what's in the database.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    }},
]
DISPATCH = {"lookup": lookup, "list_all": list_all}

SYSTEM = """You are a materials screening assistant.
When given filtering criteria, systematically check all materials step by step:
1. First list all available materials
2. Check each material against the criteria one property at a time
3. Only report materials that satisfy ALL criteria
Do not guess values — always use tools."""

MAX_TURNS = 15  # ← 安全阀，防止死循环

def run(question: str) -> str:
    messages = [{"role": "user", "content": question}]
    turn = 0

    while turn < MAX_TURNS:
        turn += 1
        r = call(messages, system=SYSTEM, tools=TOOLS, max_tokens=1024)
        print(f"\n  [Turn {turn}] finish={r.finish_reason}  {r.summary()}")

        # ── 模型说"我做完了" ──────────────────────────────────────────────
        if r.finish_reason == "stop":
            return r.text

        # ── 模型要调工具 ──────────────────────────────────────────────────
        if r.finish_reason != "tool_calls":
            return f"[unexpected finish_reason: {r.finish_reason}]\n{r.text}"

        for tu in r.tool_uses:
            print(f"      → {tu['name']}({tu['input']})")

        # 把模型的 tool_call 消息存入 messages
        raw = r.raw.choices[0].message
        messages.append({
            "role": "assistant",
            "content": raw.content,
            "tool_calls": [tc.model_dump() for tc in (raw.tool_calls or [])],
        })

        # 执行工具，结果存入 messages
        for tu in r.tool_uses:
            result = DISPATCH.get(tu["name"], lambda **_: {"error": "unknown tool"})(**tu["input"])
            print(f"      ← {result}")
            messages.append({
                "role": "tool",
                "tool_call_id": tu["id"],
                "content": json.dumps(result, ensure_ascii=False),
            })

    return "[max turns reached]"

if __name__ == "__main__":
    q = "帮我筛选材料：密度要小于 4000 kg/m³，同时杨氏模量要大于 100 GPa。符合条件的有哪些？"
    print(f"Q: {q}")
    print(f"A: {run(q)}")
