"""Run the eval suite against ex1_materials agent and produce a baseline report.

用法:
    uv run python phase1_patterns/01_augmented_llm/run_eval.py

会产出:
    eval_baseline.json   ← 第一次运行时作为基线
    eval_latest.json     ← 每次运行更新（后续可和基线对比）

后续改动 agent 后再跑这个脚本，会自动和 baseline 对比，看你的改动是 improve 还是 regress。
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))

from shared.eval import (
    run_eval, default_scorer,
    print_report, save_report, load_report, compare_reports,
)
from shared.eval.instrumented import AgentConfig, build_instrumented_agent

# 复用 ex1_materials 的工具和 dispatch（SYSTEM 单独管理以便迭代）
from ex1_materials import TOOLS, DISPATCH
from eval_set import EVAL_SET


# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM Prompt 版本管理
# v1 已在 eval_baseline.json 里固化，不需要再在代码里保留
# ─────────────────────────────────────────────────────────────────────────────

# v2: 显式指导 found=false 时的处理（current production）
SYSTEM_V2 = (
    "You are a materials science assistant. "
    "Always use tools for property data — never recall from memory. "
    "Report values with units. "
    "If a tool returns found=false, you MUST: "
    "(1) tell the user the requested material is not in the database, "
    "(2) list the available materials from the tool's 'available' field, "
    "(3) NEVER guess values when found=false."
)

ACTIVE_SYSTEM = SYSTEM_V2
ACTIVE_VERSION = "v2"
REPEAT = 3   # >1 时统计 pass rate


# Pattern 01 = 最多 2 轮（R1 拿工具，R2 强制收尾）
# 由 build_instrumented_agent 用 drop_tools_in_final_round=True 实现
instrumented_agent = build_instrumented_agent(AgentConfig(
    system=ACTIVE_SYSTEM,
    tools=TOOLS,
    dispatch=DISPATCH,
    max_turns=2,
    max_tokens=512,
    drop_tools_in_final_round=True,
))


def main() -> None:
    out_dir = Path(__file__).parent
    baseline_path = out_dir / "eval_baseline.json"
    latest_path = out_dir / "eval_latest.json"

    print(f"\n► Running {len(EVAL_SET)} cases × {REPEAT} repeats against ex1_materials agent "
          f"(qwen3.6-plus, SYSTEM={ACTIVE_VERSION})...\n"
          f"  Total LLM calls expected: ~{len(EVAL_SET) * REPEAT * 2}  "
          f"(each case = 1-2 calls × {REPEAT} runs)\n")

    report = run_eval(
        agent_fn=instrumented_agent,
        dataset=EVAL_SET,
        scoring_fn=default_scorer,
        repeat=REPEAT,
        verbose=True,
    )

    print_report(report)
    save_report(report, latest_path)

    if not baseline_path.exists():
        save_report(report, baseline_path)
        print("  ℹ️  这是第一次运行，已作为 baseline 保存。\n"
              "     后续改动 agent 后再跑此脚本，会自动和 baseline 对比。")
    else:
        baseline = load_report(baseline_path)
        compare_reports(baseline, report)


if __name__ == "__main__":
    main()
