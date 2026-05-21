"""跑全部 dogfood 问题，捕获完整结果到 results.json。

运行：
  uv run python -m dogfood.run

输出：
  dogfood/results.json — 每个 case 的完整结果（含答案、tools、cost、latency）
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.eval.instrumented import AgentConfig, build_instrumented_agent
from stage2.agent_stage2 import TOOLS, SYSTEM, DISPATCH, MAX_TURNS
from dogfood.questions import QUESTIONS


# 用 Stage 2 RAG agent（已经过 v2 SYSTEM 优化）
agent = build_instrumented_agent(AgentConfig(
    system=SYSTEM,
    tools=TOOLS,
    dispatch=DISPATCH,
    max_turns=MAX_TURNS,
    max_tokens=1024,
))


def main() -> None:
    out_path = Path(__file__).parent / "results.json"
    results = []
    total_start = time.time()

    print(f"\n{'═' * 70}")
    print(f"  DOGFOOD: {len(QUESTIONS)} 个 PhD 级别问题")
    print(f"{'═' * 70}\n")

    for i, q in enumerate(QUESTIONS, 1):
        print(f"\n[{i}/{len(QUESTIONS)}] {q.id}")
        print(f"  Q: {q.question[:100]}{'...' if len(q.question) > 100 else ''}")
        print(f"  预期 pain point: {q.expected_pain_point}")
        print(f"  ─── 运行中 ───")

        start = time.time()
        try:
            response = agent(q.question)
            duration = time.time() - start
            tools_called = [tc["name"] for tc in response.tool_calls]
            tool_counter: dict[str, int] = {}
            for t in tools_called:
                tool_counter[t] = tool_counter.get(t, 0) + 1

            results.append({
                "id": q.id,
                "question": q.question,
                "why_realistic": q.why_realistic,
                "expected_pain_point": q.expected_pain_point,
                "answer": response.text,
                "turns": response.turns,
                "tool_calls_total": len(response.tool_calls),
                "tools_breakdown": tool_counter,
                "cost_usd": response.cost_usd,
                "duration_sec": round(duration, 1),
                "finish_reason": response.finish_reason,
                "completed": response.finish_reason == "stop",
            })
            mark = "✓" if response.finish_reason == "stop" else "⚠"
            print(f"  {mark} {duration:.1f}s / ${response.cost_usd:.4f} / "
                  f"{len(response.tool_calls)} tools / {response.turns} turns")
            print(f"     answer preview: {response.text[:150].replace(chr(10), ' ')}...")
        except Exception as e:
            print(f"  ❌ exception: {type(e).__name__}: {e}")
            results.append({
                "id": q.id,
                "question": q.question,
                "error": f"{type(e).__name__}: {e}",
                "completed": False,
            })

    total_duration = time.time() - total_start
    total_cost = sum(r.get("cost_usd", 0) for r in results)
    completed = sum(1 for r in results if r.get("completed"))

    print(f"\n{'═' * 70}")
    print(f"  Summary: {completed}/{len(QUESTIONS)} completed")
    print(f"  Total time:  {total_duration / 60:.1f} min")
    print(f"  Total cost:  ${total_cost:.4f}")
    print(f"  Avg cost:    ${total_cost / len(QUESTIONS):.4f} / question")
    print(f"  Avg latency: {total_duration / len(QUESTIONS):.1f} sec / question")
    print(f"{'═' * 70}\n")

    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"  → {out_path}")


if __name__ == "__main__":
    main()
