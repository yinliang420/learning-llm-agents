"""Run eval against Stage 2 agent (RAG-enabled), compare to Stage 1 baseline."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # 让能 import eval_set

from shared.eval import (
    run_eval, default_scorer,
    print_report, save_report, load_report, compare_reports,
)
from shared.eval.instrumented import AgentConfig, build_instrumented_agent
from eval_set import EVAL_SET                                   # 复用 Stage 1 的 15 cases
from stage2.agent_stage2 import TOOLS, SYSTEM, DISPATCH, MAX_TURNS


REPEAT = 1


# 把 agent 配置参数化，统一用 shared/eval/instrumented.py 的 loop
instrumented_agent = build_instrumented_agent(AgentConfig(
    system=SYSTEM,
    tools=TOOLS,
    dispatch=DISPATCH,
    max_turns=MAX_TURNS,
    max_tokens=1024,
))


def main() -> None:
    out_dir = Path(__file__).parent
    baseline_path = Path(__file__).resolve().parent.parent / "eval_baseline.json"
    stage2_path = out_dir / "eval_stage2.json"

    print(f"\n► Stage 2 eval: {len(EVAL_SET)} cases × {REPEAT} run (RAG-enabled agent)\n")

    report = run_eval(
        agent_fn=instrumented_agent,
        dataset=EVAL_SET,
        scoring_fn=default_scorer,
        repeat=REPEAT,
        verbose=True,
    )

    print_report(report)
    save_report(report, stage2_path)

    if baseline_path.exists():
        baseline = load_report(baseline_path)
        print(f"\n  ▼ Comparison vs Stage 1 baseline ({baseline_path.name})")
        compare_reports(baseline, report)
    else:
        print(f"  ℹ️  No Stage 1 baseline found at {baseline_path}")


if __name__ == "__main__":
    main()
