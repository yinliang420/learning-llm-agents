"""Run eval against paper_qa Stage 1 agent.

第一次跑会作为 baseline 保存。之后改 agent 重跑会自动 diff baseline。
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

# 复用 agent.py 的 SYSTEM 作为 v1 base，本文件管理 v2 改进
from agent import TOOLS, SYSTEM as SYSTEM_V1, MAX_TURNS
from tools import DISPATCH
from eval_set import EVAL_SET


# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM Prompt 版本管理（同 01_augmented_llm 的迭代模式）
# ─────────────────────────────────────────────────────────────────────────────

# v2 = 针对 baseline 暴露的 cost outlier 做的改进
#      问题：out_of_scope_topic case 跑了 9 次 search_in_paper，190 秒 / $0.002
#      改进：明确指导"超出范围的话题快速判断，不要逐篇搜索"
SYSTEM_V2 = SYSTEM_V1 + """

EFFICIENCY GUIDELINES (added in v2 to reduce wasteful exhaustive searches):
- For out-of-scope questions (topics clearly not in the collection based on titles/previews),
  use list_papers ONCE and judge from previews. Do NOT search each paper exhaustively.
- For "which paper covers X" questions, the first_page_preview is usually enough.
  Only read_paper if the preview is genuinely ambiguous.
- Reserve search_in_paper for verifying a SPECIFIC term in 1-2 candidate papers,
  not for checking if a topic exists across all papers."""

ACTIVE_SYSTEM = SYSTEM_V2
ACTIVE_VERSION = "v2"
REPEAT = 1   # 单次跑做 baseline；改 SYSTEM 时再上 repeat=3 看 flake


# 把 agent 配置参数化，统一用 shared/eval/instrumented.py 的 loop
# 注：MODEL 默认走 LLM_MODEL env（qwen-plus），如需对比换 model 改这一行
instrumented_agent = build_instrumented_agent(AgentConfig(
    system=ACTIVE_SYSTEM,
    tools=TOOLS,
    dispatch=DISPATCH,
    max_turns=MAX_TURNS,
    max_tokens=1024,
))


def main() -> None:
    out_dir = Path(__file__).parent
    baseline_path = out_dir / "eval_baseline.json"
    latest_path = out_dir / "eval_latest.json"

    print(f"\n► Running {len(EVAL_SET)} cases × {REPEAT} repeats against paper_qa agent "
          f"(SYSTEM={ACTIVE_VERSION})...\n"
          f"  Expected: ~{len(EVAL_SET) * REPEAT * 2.5:.0f} LLM calls, "
          f"~{len(EVAL_SET) * REPEAT * 20 / 60:.0f} minutes\n")

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
        print("  ℹ️  第一次运行，已存为 baseline。后续改 agent 重跑会自动 diff。\n")
    else:
        baseline = load_report(baseline_path)
        compare_reports(baseline, report)


if __name__ == "__main__":
    main()
