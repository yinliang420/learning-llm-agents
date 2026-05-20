"""Eval 框架的数据类型定义。

设计原则：
  - 所有 dataclass 不依赖其他模块（除标准库），避免 import 循环
  - properties 用于聚合/派生，原始数据存字段
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EvalCase:
    """一个测试用例。"""
    id: str
    input: str
    expected: dict
    tags: list[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class AgentResponse:
    """instrumented agent 返回的完整信息。"""
    text: str
    tool_calls: list[dict] = field(default_factory=list)
    cost_usd: float = 0.0
    duration_ms: int = 0
    turns: int = 0
    finish_reason: str = ""


@dataclass
class RunAttempt:
    """单次执行结果（一个 case 可能跑多次）。"""
    actual: AgentResponse
    passed: bool
    score: float
    failures: list[str] = field(default_factory=list)


@dataclass
class CaseResult:
    """一个 case 的完整结果（含所有 repeat 次运行）。"""
    case_id: str
    input: str
    expected: dict
    runs: list[RunAttempt] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    @property
    def total_runs(self) -> int:
        return len(self.runs)

    @property
    def pass_count(self) -> int:
        return sum(1 for r in self.runs if r.passed)

    @property
    def pass_rate(self) -> float:
        return self.pass_count / self.total_runs if self.total_runs else 0.0

    @property
    def passed(self) -> bool:
        """严格通过 = 所有 run 都过。"""
        return self.pass_rate >= 1.0

    @property
    def flaky(self) -> bool:
        """既不是全通过也不是全失败 → 不稳定。"""
        return 0.0 < self.pass_rate < 1.0

    @property
    def fully_failed(self) -> bool:
        return self.pass_rate == 0.0

    @property
    def actual(self) -> AgentResponse:
        """back-compat：返回第一次运行的结果。"""
        return self.runs[0].actual if self.runs else AgentResponse(text="")

    @property
    def score(self) -> float:
        """各 run score 的平均。"""
        return sum(r.score for r in self.runs) / self.total_runs if self.total_runs else 0.0

    @property
    def failures(self) -> list[str]:
        """跨所有 run 收集去重后的失败原因。"""
        seen: set[str] = set()
        result: list[str] = []
        for r in self.runs:
            for f in r.failures:
                if f not in seen:
                    seen.add(f)
                    result.append(f)
        return result

    @property
    def avg_cost(self) -> float:
        return sum(r.actual.cost_usd for r in self.runs) / self.total_runs if self.total_runs else 0.0

    @property
    def avg_duration_ms(self) -> float:
        return sum(r.actual.duration_ms for r in self.runs) / self.total_runs if self.total_runs else 0.0

    @property
    def avg_turns(self) -> float:
        return sum(r.actual.turns for r in self.runs) / self.total_runs if self.total_runs else 0.0


@dataclass
class EvalReport:
    """一次完整 eval 运行的聚合报告。"""
    cases: list[CaseResult]
    timestamp: str
    repeat: int = 1
    metadata: dict = field(default_factory=dict)

    @property
    def total(self) -> int:
        return len(self.cases)

    @property
    def total_runs(self) -> int:
        return sum(c.total_runs for c in self.cases)

    @property
    def passed(self) -> int:
        """完全通过的 case 数（所有 run 都过）。"""
        return sum(1 for c in self.cases if c.passed)

    @property
    def flaky_count(self) -> int:
        """flaky case 数（部分通过部分失败）。"""
        return sum(1 for c in self.cases if c.flaky)

    @property
    def failed_count(self) -> int:
        """完全失败的 case 数。"""
        return sum(1 for c in self.cases if c.fully_failed)

    @property
    def accuracy(self) -> float:
        """严格准确率：完全通过的 case 比例。"""
        return self.passed / self.total if self.total else 0.0

    @property
    def mean_pass_rate(self) -> float:
        """平均 pass rate：所有 case pass_rate 的算术平均（更细粒度）。"""
        return sum(c.pass_rate for c in self.cases) / self.total if self.total else 0.0

    @property
    def total_cost(self) -> float:
        """所有 run 的累计成本。"""
        return sum(r.actual.cost_usd for c in self.cases for r in c.runs)

    @property
    def avg_duration_ms(self) -> float:
        """单 run 的平均延迟。"""
        all_durations = [r.actual.duration_ms for c in self.cases for r in c.runs]
        return sum(all_durations) / len(all_durations) if all_durations else 0.0

    @property
    def avg_turns(self) -> float:
        all_turns = [r.actual.turns for c in self.cases for r in c.runs]
        return sum(all_turns) / len(all_turns) if all_turns else 0.0

    def failure_modes(self) -> dict[str, int]:
        """按 tag 统计完全失败的 case 数。"""
        modes: dict[str, int] = {}
        for c in self.cases:
            if c.fully_failed or c.flaky:
                for tag in (c.tags or ["untagged"]):
                    modes[tag] = modes.get(tag, 0) + 1
        return modes
