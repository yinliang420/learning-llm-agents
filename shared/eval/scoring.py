"""Eval 打分函数。

设计：scoring_fn 输入 (AgentResponse, expected dict)，输出 (passed, score, failures)。
"""
from __future__ import annotations

from .types import AgentResponse


def default_scorer(response: AgentResponse, expected: dict) -> tuple[bool, float, list[str]]:
    """通用打分器。expected dict 支持以下 key：

    - "contains_all":  list[str]  答案文本必须包含所有这些子串
    - "contains_any":  list[str]  答案文本至少包含其中一个子串
    - "not_contains":  list[str]  答案文本不能包含任何这些子串
    - "no_tool":       bool       agent 不应该调任何工具
    - "expected_tool": str        agent 必须调用这个工具
    - "min_tools":     int        agent 至少调了 N 个工具
    """
    failures: list[str] = []
    text = (response.text or "").lower()

    if "contains_all" in expected:
        for s in expected["contains_all"]:
            if s.lower() not in text:
                failures.append(f"missing required substring: '{s}'")

    if "contains_any" in expected:
        if not any(s.lower() in text for s in expected["contains_any"]):
            failures.append(f"none of {expected['contains_any']} appeared")

    if "not_contains" in expected:
        for s in expected["not_contains"]:
            if s.lower() in text:
                failures.append(f"forbidden substring present: '{s}'")

    called = [tc["name"] for tc in response.tool_calls]

    if expected.get("no_tool") and called:
        failures.append(f"expected NO tool call, got {called}")

    if "expected_tool" in expected:
        if expected["expected_tool"] not in called:
            failures.append(f"expected tool '{expected['expected_tool']}' not called, got {called or 'none'}")

    if "min_tools" in expected:
        if len(called) < expected["min_tools"]:
            failures.append(f"expected ≥{expected['min_tools']} tool calls, got {len(called)}")

    passed = not failures
    score = 1.0 if passed else 0.0
    return passed, score, failures
