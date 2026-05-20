"""Eval runner — 跑 agent 经过 dataset，打分聚合成 report。"""
from __future__ import annotations

import time
from collections.abc import Iterable
from datetime import datetime
from typing import Callable

from .types import AgentResponse, CaseResult, EvalCase, EvalReport, RunAttempt


def run_eval(
    agent_fn: Callable[[str], AgentResponse],
    dataset: Iterable[EvalCase],
    scoring_fn: Callable[[AgentResponse, dict], tuple[bool, float, list[str]]],
    repeat: int = 1,
    verbose: bool = True,
) -> EvalReport:
    """跑 agent 经过 dataset，用 scoring_fn 打分。

    Args:
        agent_fn:    输入 question 字符串，输出 AgentResponse
        dataset:     EvalCase 列表
        scoring_fn:  (actual, expected) → (passed, score, failures)
        repeat:      每个 case 重复运行次数（默认 1）
                     > 1 时可以识别 flaky case
    """
    results: list[CaseResult] = []
    cases = list(dataset)

    for i, case in enumerate(cases, 1):
        case_result = CaseResult(
            case_id=case.id, input=case.input,
            expected=case.expected, tags=case.tags,
        )

        for attempt in range(1, repeat + 1):
            if verbose:
                tag = f"[{i}/{len(cases)}]" if repeat == 1 else f"[{i}/{len(cases)}·{attempt}/{repeat}]"
                print(f"\n  {tag} {case.id}: {case.input}")

            start = time.time()
            try:
                response = agent_fn(case.input)
            except Exception as e:
                response = AgentResponse(text=f"[EXCEPTION] {e}", finish_reason="error")

            if not response.duration_ms:
                response.duration_ms = int((time.time() - start) * 1000)

            passed, score, failures = scoring_fn(response, case.expected)

            case_result.runs.append(RunAttempt(
                actual=response, passed=passed, score=score, failures=failures,
            ))

            if verbose:
                status = "✓" if passed else "✗"
                preview = (response.text or "").replace("\n", " ")[:80]
                tools = ",".join(tc["name"] for tc in response.tool_calls) or "—"
                print(f"      {status} tools=[{tools}] cost=${response.cost_usd:.6f} {response.duration_ms}ms")
                print(f"        {preview}")
                for f in failures:
                    print(f"        ↳ {f}")

        # 跑完一个 case 的所有 repeat
        if verbose and repeat > 1:
            pr = case_result.pass_rate
            marker = "✅" if pr == 1.0 else ("⚠️ flaky" if pr > 0 else "❌")
            print(f"      └─ {marker} pass_rate = {case_result.pass_count}/{case_result.total_runs}")

        results.append(case_result)

    return EvalReport(cases=results, timestamp=datetime.now().isoformat(), repeat=repeat)
