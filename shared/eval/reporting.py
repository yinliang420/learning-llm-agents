"""Report 打印、序列化、对比。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .types import AgentResponse, CaseResult, EvalReport, RunAttempt


def print_report(report: EvalReport, show_failures: bool = True) -> None:
    """打印 eval 报告。多 run 时显示 pass_rate 和 flakiness。"""
    W = 64
    print("\n" + "═" * W)
    print(f"  Eval Report — {report.timestamp[:19]}  (repeat={report.repeat})")
    print("═" * W)
    print(f"  Cases × runs : {report.total} × {report.repeat} = {report.total_runs} executions")
    print(f"  Fully passed : {report.passed} / {report.total} ({report.accuracy:.1%})")
    print(f"  Flaky        : {report.flaky_count}")
    print(f"  Fully failed : {report.failed_count}")
    if report.repeat > 1:
        print(f"  Mean pass rate: {report.mean_pass_rate:.1%}  (per-case avg)")
    print(f"  Total cost   : ${report.total_cost:.6f}")
    print(f"  Avg latency  : {report.avg_duration_ms:.0f} ms / run")
    print(f"  Avg turns    : {report.avg_turns:.1f}")

    fm = report.failure_modes()
    if fm:
        print("\n  Problematic cases by tag (flaky + fully_failed):")
        for tag, count in sorted(fm.items(), key=lambda x: -x[1]):
            print(f"    • {tag}: {count}")

    if show_failures:
        flaky = [c for c in report.cases if c.flaky]
        failed = [c for c in report.cases if c.fully_failed]

        if flaky:
            print(f"\n  ⚠️  Flaky cases ({len(flaky)}):")
            for c in flaky:
                print(f"    [{c.case_id}] pass_rate={c.pass_count}/{c.total_runs}  Q: {c.input}")
                for f in c.failures[:3]:
                    print(f"      ↳ {f}")

        if failed:
            print(f"\n  ❌ Fully failed cases ({len(failed)}):")
            for c in failed:
                tools = ",".join(tc["name"] for tc in c.actual.tool_calls) or "—"
                print(f"    [{c.case_id}]  tools=[{tools}]")
                print(f"      Q: {c.input}")
                print(f"      A: {(c.actual.text or '').strip()[:120]}")
                for f in c.failures[:3]:
                    print(f"      ↳ {f}")
    print("═" * W + "\n")


def _serialize(obj: Any) -> Any:
    """递归把 dataclass / 对象转成可 JSON 序列化的 dict。"""
    if hasattr(obj, "__dict__"):
        return {k: _serialize(v) for k, v in obj.__dict__.items() if k != "raw"}
    if isinstance(obj, (list, tuple)):
        return [_serialize(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    return obj


def save_report(report: EvalReport, path: str | Path) -> None:
    """把报告存成 JSON，便于以后 diff。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = _serialize(report)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    print(f"  → saved: {path}")


def load_report(path: str | Path) -> EvalReport:
    """从 JSON 加载报告。兼容旧版（无 runs 字段）和新版。"""
    data = json.loads(Path(path).read_text())
    cases = []
    for c in data["cases"]:
        if "runs" in c:
            runs = [
                RunAttempt(
                    actual=AgentResponse(**r["actual"]),
                    passed=r["passed"], score=r["score"],
                    failures=r.get("failures", []),
                )
                for r in c["runs"]
            ]
        else:
            runs = [RunAttempt(
                actual=AgentResponse(**c["actual"]),
                passed=c["passed"], score=c["score"],
                failures=c.get("failures", []),
            )]
        cases.append(CaseResult(
            case_id=c["case_id"], input=c["input"],
            expected=c["expected"], tags=c.get("tags", []),
            runs=runs,
        ))
    return EvalReport(
        cases=cases,
        timestamp=data["timestamp"],
        repeat=data.get("repeat", 1),
        metadata=data.get("metadata", {}),
    )


def compare_reports(baseline: EvalReport, current: EvalReport) -> None:
    """diff 两份报告：改进 / 回归 / flake 变化。"""
    b_map = {c.case_id: c for c in baseline.cases}
    c_map = {c.case_id: c for c in current.cases}

    improved, regressed = [], []
    became_stable, became_flaky = [], []
    rate_changes: list[tuple[str, float, float]] = []

    for cid in set(b_map) | set(c_map):
        b, c = b_map.get(cid), c_map.get(cid)
        if not b or not c:
            continue

        if abs(c.pass_rate - b.pass_rate) > 0.001:
            rate_changes.append((cid, b.pass_rate, c.pass_rate))

        if not b.passed and c.passed:
            improved.append(cid)
        elif b.passed and not c.passed:
            regressed.append(cid)

        if b.flaky and not c.flaky:
            became_stable.append((cid, c.pass_rate))
        elif not b.flaky and c.flaky:
            became_flaky.append((cid, c.pass_count, c.total_runs))

    W = 64
    print("\n" + "═" * W)
    print(f"  Comparison: baseline (repeat={baseline.repeat}) → current (repeat={current.repeat})")
    print("═" * W)
    print(f"  Accuracy       : {baseline.accuracy:.1%} → {current.accuracy:.1%}   ({current.accuracy - baseline.accuracy:+.1%})")
    print(f"  Mean pass rate : {baseline.mean_pass_rate:.1%} → {current.mean_pass_rate:.1%}   ({current.mean_pass_rate - baseline.mean_pass_rate:+.1%})")
    print(f"  Flaky cases    : {baseline.flaky_count} → {current.flaky_count}")
    print(f"  Cost           : ${baseline.total_cost:.6f} → ${current.total_cost:.6f}")
    print(f"  Latency        : {baseline.avg_duration_ms:.0f}ms → {current.avg_duration_ms:.0f}ms")

    if improved:
        print(f"\n  ✅ Fully passing now ({len(improved)}):")
        for cid in improved:
            print(f"    + {cid}")
    if regressed:
        print(f"\n  🔴 Regressed ({len(regressed)}):")
        for cid in regressed:
            print(f"    - {cid}: {b_map[cid].input}")
    if became_stable:
        print(f"\n  ✨ Became stable ({len(became_stable)}):")
        for cid, rate in became_stable:
            print(f"    + {cid} (now {rate:.0%})")
    if became_flaky:
        print(f"\n  ⚠️  Became flaky ({len(became_flaky)}):")
        for cid, pc, tot in became_flaky:
            print(f"    - {cid} (now {pc}/{tot})")

    if rate_changes:
        rate_changes.sort(key=lambda x: x[2] - x[1])
        print(f"\n  Pass rate changes:")
        for cid, b_rate, c_rate in rate_changes[:5]:
            delta = c_rate - b_rate
            arrow = "↑" if delta > 0 else "↓"
            print(f"    {arrow} {cid}: {b_rate:.0%} → {c_rate:.0%}  ({delta:+.0%})")
    print("═" * W + "\n")
