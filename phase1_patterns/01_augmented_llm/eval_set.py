"""Eval set for ex1_materials — 10 cases covering happy paths, edges, error handling."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from shared.eval import EvalCase


EVAL_SET: list[EvalCase] = [
    # ── Happy path: 单次工具调用 ─────────────────────────────────────────────
    EvalCase(
        id="single_steel_density",
        input="钢的密度是多少？",
        expected={
            "contains_all": ["7850", "kg/m³"],
            "expected_tool": "lookup",
        },
        tags=["happy_path", "single_lookup"],
        notes="基础查询：模型应该调 lookup 并报告数值+单位",
    ),
    EvalCase(
        id="single_sic_modulus",
        input="SiC 的杨氏模量是多少？",
        expected={
            "contains_all": ["410", "GPa"],
            "expected_tool": "lookup",
        },
        tags=["happy_path", "single_lookup"],
    ),

    # ── Happy path: 并行调用 ────────────────────────────────────────────────
    EvalCase(
        id="parallel_density_compare",
        input="SiC 和铝的密度分别是多少，谁更轻？",
        expected={
            "contains_all": ["3210", "2700"],
            "contains_any": ["铝", "aluminium"],
            "expected_tool": "lookup",
            "min_tools": 2,
        },
        tags=["happy_path", "parallel_lookup"],
        notes="并行调两次 lookup，模型应该比较后得出铝更轻",
    ),
    EvalCase(
        id="parallel_hardness_compare",
        input="SiC 和钢哪个更硬？",
        expected={
            "contains_any": ["sic", "碳化硅"],
            "expected_tool": "lookup",
            "min_tools": 2,
        },
        tags=["happy_path", "parallel_lookup"],
        notes="SiC 2500 HV >> 钢 130 HB",
    ),

    # ── Discovery: 调用 list_all ─────────────────────────────────────────────
    EvalCase(
        id="list_materials",
        input="你的数据库里有哪些材料可以查？",
        expected={
            "contains_all": ["steel", "aluminium", "sic"],
            "expected_tool": "list_all",
        },
        tags=["happy_path", "discovery"],
    ),

    # ── 错误处理：DB 里没有的材料 ───────────────────────────────────────────
    EvalCase(
        id="missing_material_tungsten",
        input="钨的熔点是多少？",
        expected={
            "contains_any": ["没有", "不在", "not", "available", "支持", "数据库中"],
            "not_contains": ["3422", "3,422"],  # 钨真实熔点，模型不应该自己编
        },
        tags=["error_handling", "missing_material"],
        notes="数据库无钨，模型应优雅告知，不能从训练记忆编造数值",
    ),

    # ── 概念题：不应该调工具 ────────────────────────────────────────────────
    EvalCase(
        id="conceptual_no_tool",
        input="什么是杨氏模量？请简短解释。",
        expected={
            "contains_any": ["刚度", "弹性", "stiffness", "应力", "应变"],
            "no_tool": True,
        },
        tags=["edge_case", "conceptual"],
        notes="纯概念问题，模型应该直接回答，不调任何工具",
    ),
    EvalCase(
        id="conceptual_unit",
        input="GPa 和 MPa 之间是什么关系？只回答关系，不查材料。",
        expected={
            "contains_any": ["1000", "10³", "千", "thousand"],
            "no_tool": True,
        },
        tags=["edge_case", "conceptual"],
    ),

    # ── 混合型：lookup + 计算 ──────────────────────────────────────────────
    EvalCase(
        id="compute_after_lookup",
        input="SiC 的杨氏模量是钢的几倍？",
        expected={
            "contains_any": ["2.0", "2倍", "两倍", "2 倍", "约为 2", "2.05"],  # 410/200 ≈ 2.05
            "expected_tool": "lookup",
            "min_tools": 2,
        },
        tags=["mixed_type", "compute_after_lookup"],
        notes="需要查两个值再做除法。Pattern 01 缺 calculate 工具，要模型自己算",
    ),

    # ── 跨语言：英文提问 ───────────────────────────────────────────────────
    EvalCase(
        id="english_query",
        input="What's the melting point of titanium?",
        expected={
            "contains_all": ["1668"],
            "contains_any": ["°c", "celsius"],
            "expected_tool": "lookup",
        },
        tags=["edge_case", "language"],
        notes="英文提问，模型应正确把 titanium 作为参数传给 lookup",
    ),
]
