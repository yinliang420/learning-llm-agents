"""
Pattern 01 — Example 2: Scientific Calculator
==============================================

Augmented LLM: 模型 + 计算工具。

与 Example 1 的本质区别：
  - Example 1 的工具是"查数据"（lookup）—— 工具只读
  - Example 2 的工具是"做计算"（compute）—— 工具执行代码

重点：
  1. 工具可以执行真实逻辑（eval、API 调用、写文件……）
  2. 模型决定"是否需要精确计算"还是"可以直接回答"
  3. 错误结果也要回传给模型，让模型尝试修正

运行: uv run python phase1_patterns/01_augmented_llm/ex2_calculator.py
"""

from __future__ import annotations
import json, math, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from shared.llm import call

# ── 工具函数 ─────────────────────────────────────────────────────────────────

# 允许在表达式里使用的数学函数/常量
_MATH_SCOPE = {k: v for k, v in math.__dict__.items() if not k.startswith("_")}
_MATH_SCOPE.update({"abs": abs, "round": round, "min": min, "max": max})

def calculate(expression: str) -> dict:
    """
    执行数学表达式。支持 math 标准库的所有函数。

    ⚠️  安全警告：CPython 的 eval 沙箱并不可靠。
    {"__builtins__": {}} 能挡住简单攻击，但不能挡住
    `().__class__.__bases__[0].__subclasses__()` 这类 MRO 遍历，
    仍然可以访问系统级类。
    → 学习阶段可用；生产环境请用 subprocess 隔离或专门的沙箱（e2b 等）。
    """
    try:
        result = eval(expression, {"__builtins__": {}}, _MATH_SCOPE)  # noqa: S307
        return {"ok": True, "expression": expression, "result": float(result)}
    except ZeroDivisionError:
        return {"ok": False, "expression": expression, "error": "division by zero"}
    except Exception as e:
        return {"ok": False, "expression": expression, "error": str(e)}

# ── 工具 Schema ───────────────────────────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": (
                "Evaluate a mathematical expression and return the numeric result. "
                "Use for any arithmetic, unit conversions, or formula evaluations "
                "where an exact number is needed. "
                "Supports standard Python math: +, -, *, /, **, sqrt(), log(), "
                "sin(), cos(), pi, e, etc. "
                "Do NOT use for symbolic algebra or expressions with unknowns."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": (
                            "A valid Python math expression. "
                            "Examples: '200 * 1000', '7850 * 2 * 3 * 0.01', 'sqrt(2)', '200e9 / 7850'"
                        ),
                    }
                },
                "required": ["expression"],
            },
        },
    }
]

# ── Agent ─────────────────────────────────────────────────────────────────────

SYSTEM = (
    "You are a scientific calculator assistant. "
    "When exact numerical results are needed, use the calculate tool. "
    "Show the expression you used and explain the result with proper units. "
    "For purely conceptual questions, answer directly without the tool."
)

def run(question: str) -> str:
    messages = [{"role": "user", "content": question}]

    r1 = call(messages, system=SYSTEM, tools=TOOLS, max_tokens=512)
    print(f"  [R1] finish={r1.finish_reason}  {r1.summary()}")

    if r1.finish_reason != "tool_calls":
        return r1.text

    for tu in r1.tool_uses:
        print(f"      → {tu['name']}({tu['input']})")

    raw = r1.raw.choices[0].message
    messages.append({
        "role": "assistant",
        "content": raw.content,
        "tool_calls": [tc.model_dump() for tc in (raw.tool_calls or [])],
    })

    for tu in r1.tool_uses:
        result = calculate(**tu["input"])
        print(f"      ← {result}")
        messages.append({
            "role": "tool",
            "tool_call_id": tu["id"],
            "content": json.dumps(result, ensure_ascii=False),
        })

    r2 = call(messages, system=SYSTEM, max_tokens=512)
    print(f"  [R2] finish={r2.finish_reason}  {r2.summary()}")
    return r2.text


# ── 测试问题 ──────────────────────────────────────────────────────────────────

QUESTIONS = [
    # 单位换算
    "200 GPa 等于多少 MPa？",
    # 物理公式（σ = F/A）
    "一块截面积 0.002 m² 的钢棒受到 50000 N 的拉力，应力是多少 MPa？",
    # 体积 × 密度 → 质量
    "一块 2m × 0.5m × 0.01m 的铝板（密度 2700 kg/m³），质量是多少 kg？",
    # 比刚度（需要模型自己组合计算）
    "SiC 的 Young's modulus 是 410 GPa，密度是 3210 kg/m³，比刚度（E/ρ）是多少 MN·m/kg？",
    # 无需计算，直接回答（观察模型是否跳过工具）
    "应力和应变有什么区别？",
    # 故意除以零（测试错误回传）
    "1 除以 0 是多少？",
]

if __name__ == "__main__":
    for q in QUESTIONS:
        print(f"\n{'='*60}")
        print(f"Q: {q}")
        print(f"A: {run(q)}")
