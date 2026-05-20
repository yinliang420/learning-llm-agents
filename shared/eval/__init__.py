"""Minimal but real eval framework for agents.

使用方式：
    from shared.eval import EvalCase, AgentResponse, run_eval, default_scorer
    from shared.eval import print_report, save_report, compare_reports, load_report

    report = run_eval(agent_fn, dataset, scoring_fn, repeat=3)

模块组织：
    types.py        — 数据类（EvalCase / AgentResponse / RunAttempt / CaseResult / EvalReport）
    scoring.py      — default_scorer 及打分函数
    runner.py       — run_eval() 主运行器
    reporting.py    — print_report / save_report / load_report / compare_reports
    instrumented.py — 把 Pattern 02 agent 包装成可被 run_eval 调用的形式
"""
from .types import (
    AgentResponse,
    CaseResult,
    EvalCase,
    EvalReport,
    RunAttempt,
)
from .scoring import default_scorer
from .runner import run_eval
from .reporting import (
    compare_reports,
    load_report,
    print_report,
    save_report,
)

__all__ = [
    # types
    "EvalCase",
    "AgentResponse",
    "RunAttempt",
    "CaseResult",
    "EvalReport",
    # scoring
    "default_scorer",
    # runner
    "run_eval",
    # reporting
    "print_report",
    "save_report",
    "load_report",
    "compare_reports",
]
