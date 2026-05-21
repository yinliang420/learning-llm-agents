"""
Pattern 04: Plan-then-Execute
==============================

核心思路：先生成完整计划，再执行。
与 Pattern 02 的区别：
  02 = 边做边决定下一步（ReAct）
  04 = 先想清楚所有步骤，再一次性执行

优势：
  ✓ 计划可视化（人可以审查再执行）
  ✓ 独立步骤可以并行
  ✓ 长任务的进度可追踪

踩坑预警：
  计划出错 → 后续全错（没有 ReAct 那种自适应能力）
"""

from __future__ import annotations
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from shared.llm import call
from pydantic import BaseModel

DB = {
    "steel":     {"Young's modulus": (200, "GPa"), "density": (7850, "kg/m³"), "melting point": (1370, "°C"), "hardness": (130,  "HB")},
    "aluminium": {"Young's modulus": (69,  "GPa"), "density": (2700, "kg/m³"), "melting point": (660,  "°C"), "hardness": (25,   "HB")},
    "SiC":       {"Young's modulus": (410, "GPa"), "density": (3210, "kg/m³"), "melting point": (2730, "°C"), "hardness": (2500, "HV")},
    "copper":    {"Young's modulus": (110, "GPa"), "density": (8960, "kg/m³"), "melting point": (1085, "°C"), "hardness": (35,   "HB")},
    "titanium":  {"Young's modulus": (116, "GPa"), "density": (4500, "kg/m³"), "melting point": (1668, "°C"), "hardness": (70,   "HB")},
}

def lookup(material: str, property: str) -> dict:
    mat = next((k for k in DB if k.lower() == material.lower()), None)
    if not mat: return {"found": False, "error": f"'{material}' not in DB"}
    prop = next((k for k in DB[mat] if k.lower() == property.lower()), None)
    if not prop: return {"found": False, "error": f"'{property}' not found"}
    v, u = DB[mat][prop]
    return {"found": True, "material": mat, "property": prop, "value": v, "unit": u}

# ── Step 1: Planner ───────────────────────────────────────────────────────────

PLANNER_SYSTEM = """You are a research planner.
Given a materials science question, output a JSON plan as a list of lookup steps.
Each step must have: {"id": int, "material": str, "property": str}
Only plan lookups for properties needed to answer the question.
Properties available: Young's modulus, density, melting point, hardness
Output ONLY valid JSON, no explanation."""

def make_plan(question: str) -> list[dict]:
    r = call(
        [{"role": "user", "content": f"Question: {question}\n\nOutput the lookup plan as JSON array:"}],
        system=PLANNER_SYSTEM, max_tokens=512,
    )
    try:
        text = r.text.strip()
        if text.startswith("```"): text = text.split("```")[1].lstrip("json").strip()
        return json.loads(text)
    except Exception:
        return []

# ── Step 2: Execute ───────────────────────────────────────────────────────────

def execute_plan(plan: list[dict]) -> dict[int, dict]:
    results = {}
    for step in plan:
        result = lookup(step["material"], step["property"])
        results[step["id"]] = result
        print(f"  [Step {step['id']}] lookup({step['material']}, {step['property']}) → {result}")
    return results

# ── Step 3: Synthesize ────────────────────────────────────────────────────────

def synthesize(question: str, plan: list[dict], results: dict) -> str:
    data_summary = "\n".join(
        f"Step {sid}: {json.dumps(res)}" for sid, res in results.items()
    )
    prompt = f"Question: {question}\n\nData collected:\n{data_summary}\n\nAnswer the question based on this data:"
    r = call([{"role": "user", "content": prompt}],
             system="You are a materials science expert. Use only the provided data.", max_tokens=512)
    return r.text

# ── Full pipeline ─────────────────────────────────────────────────────────────

def run(question: str) -> str:
    print("\n[Phase 1: Planning]")
    plan = make_plan(question)
    for step in plan:
        print(f"  Plan step {step['id']}: lookup {step['material']} → {step['property']}")

    if not plan:
        return "[Planner failed to generate a plan]"

    print("\n[Phase 2: Executing]")
    results = execute_plan(plan)

    print("\n[Phase 3: Synthesizing]")
    return synthesize(question, plan, results)

if __name__ == "__main__":
    q = "对比 SiC、钢和钛在航空结构件上的适用性，从强度和重量两个维度分析"
    print(f"Q: {q}")
    print(f"\nA: {run(q)}")
