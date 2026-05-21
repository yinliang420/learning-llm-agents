"""Paper QA agent 的 eval set（Stage 1，针对当前 5 篇电催化论文）。

设计原则：
- 覆盖不同深度的问题（只查目录 / 看预览 / 读全文 / 跨论文 / 错误处理）
- 用 contains_any 而非 contains_all 应对回答多样性
- expected_tool 验证 agent 走对了路径
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from shared.eval import EvalCase


EVAL_SET: list[EvalCase] = [

    # ── 浅层：只查目录就够 ─────────────────────────────────────────────
    EvalCase(
        id="count_papers",
        input="我们一共有几篇论文？",
        expected={
            "contains_any": ["5", "五", "5 篇", "five"],
            "expected_tool": "list_papers",
        },
        tags=["shallow", "metadata"],
        notes="最简单的元数据问题，只需调 list_papers",
    ),

    EvalCase(
        id="longest_paper_pages",
        input="我们藏书里最长的论文有多少页？",
        expected={
            "contains_any": ["20"],
            "expected_tool": "list_papers",
        },
        tags=["shallow", "metadata"],
        notes="ChemSusChem 那篇 20 页是最长的",
    ),

    # ── 中层：根据 first-page preview 识别论文 ───────────────────────────
    EvalCase(
        id="find_iridium_paper",
        input="哪一篇论文研究的是 Iridium / 铱基催化剂？",
        expected={
            "contains_any": ["Yang", "perovskite", "钙钛矿", "Iridium", "Adv Funct"],
            "expected_tool": "list_papers",
        },
        tags=["mid", "topic_filter"],
        notes="只有 Adv Funct Materials 那篇是 Iridium 相关",
    ),

    EvalCase(
        id="find_acidic_oer",
        input="酸性介质下的 OER 研究是哪一篇？",
        expected={
            "contains_any": ["Yang", "perovskite", "Iridium", "Adv Funct", "acidic"],
        },
        tags=["mid", "topic_filter"],
        notes="同样指向 Iridium perovskite 那篇（标题含 acidic water oxidation）",
    ),

    EvalCase(
        id="find_urea_electrolysis",
        input="哪篇论文做的是尿素电解（urea electrolysis）？",
        expected={
            "contains_any": ["urea", "尿素", "ijhydene", "NiFe-LDH/MWCNTs", "2020.03.192"],
            "expected_tool": "list_papers",
        },
        tags=["mid", "topic_filter"],
        notes="IJHE 那篇标题明确写了 urea electrolysis",
    ),

    # ── 深层：需要读出具体内容（不指定 HOW，只测结果）─────────────────
    EvalCase(
        id="bifunctional_role",
        input="10.3390_catal8080328 这篇里 NiFeOx 同时催化哪两种反应？",
        expected={
            "contains_all": ["OR", "OE"],  # 题目原文用 OR/OE 缩写
            "min_tools": 1,  # ← 改进：只要求 agent 调过工具（任意），不规定哪个
            # 原来 expected_tool="read_paper" 是反模式：search_in_paper 也能拿到正确答案
        },
        tags=["deep", "specific_fact"],
        notes="标题写的是 ORR/OER bifunctional，agent 可用 read_paper 或 search_in_paper",
    ),

    # ── 跨工具：search 找特定术语 ────────────────────────────────────────
    EvalCase(
        id="overpotential_in_paper",
        input="在 10.1002_cssc.201901439 这篇里搜一下 overpotential 出现的位置",
        expected={
            "contains_any": ["overpotential", "page", "页"],
            "min_tools": 1,
        },
        tags=["mid", "search"],
        notes="主动让 agent 用 search_in_paper",
    ),

    # ── 错误处理：不存在的论文 ───────────────────────────────────────────
    EvalCase(
        id="missing_paper",
        input="10.1111_fake_paper_id 这篇论文讲了什么？",
        expected={
            "contains_any": ["not found", "没有", "不存在", "available", "未找到", "不在"],
        },
        tags=["error_handling", "missing_paper"],
        notes="不存在的 paper_id，agent 应优雅告知并列出可用",
    ),

    # ── 边界：藏书没覆盖的话题 ────────────────────────────────────────────
    EvalCase(
        id="out_of_scope_topic",
        input="我们藏书里有讨论 Pt（铂金）单原子催化剂的论文吗？",
        expected={
            "contains_any": ["没有", "not", "无", "找不到", "不涉及", "uncovered", "no paper"],
        },
        tags=["error_handling", "out_of_scope"],
        notes="5 篇藏书都不涉及 Pt 单原子，agent 不应该编造",
    ),

    # ── 跨论文：综合多个来源 ──────────────────────────────────────────────
    EvalCase(
        id="nife_papers_count",
        input="有几篇论文涉及 NiFe 基材料？分别是哪些？",
        expected={
            "contains_any": ["3", "三", "three"],
            "expected_tool": "list_papers",
        },
        tags=["mid", "cross_paper"],
        notes="cssc / ijhydene / catal8080328 三篇都是 NiFe 相关",
    ),

    # ─────────────────────────────────────────────────────────────────────
    # ★ Stage 1.5 hard cases — 推 Pattern 02 架构极限
    # ─────────────────────────────────────────────────────────────────────

    # ── HARD ①：跨论文数字对比（需要读 3 篇 + 提取精确数字 + 排序）─────
    EvalCase(
        id="hard_oer_overpotential_compare",
        input=(
            "对比三篇 NiFe 论文（cssc / ijhydene / catal8080328）里报告的 OER overpotential 数据，"
            "哪一篇报告的 OER overpotential 数值最小？给出每篇的具体数值（mV）。"
        ),
        expected={
            # 至少答案里要出现 mV 单位 + 一个明确的赢家
            "contains_any": ["mV"],
            "min_tools": 3,  # 至少要读 3 个 paper（无论 read 还是 search）
        },
        tags=["hard", "cross_paper", "numeric_extraction"],
        notes="极限测试：跨 3 篇论文提取精确数字 + 比较。Pattern 02 大概率会做但成本飙升",
    ),

    # ── HARD ②：单篇深度提取（需要找特定数值 + 单位）──────────────────
    EvalCase(
        id="hard_specific_overpotential_value",
        input="10.1002_cssc.201901439 这篇里报告的 OER overpotential 具体是多少 mV？在多少 mA/cm² 电流密度下？",
        expected={
            "contains_any": ["mV", "mA"],
            "min_tools": 1,
        },
        tags=["hard", "numeric_extraction"],
        notes="测试模型能否从论文里准确提取 'overpotential = X mV @ Y mA/cm²' 这种关键数字",
    ),

    # ── HARD ③：作者归属（需要看摘要 / 首页）─────────────────────────
    EvalCase(
        id="hard_yang_affiliation",
        input="Yang 这位通讯作者所在的研究机构是哪里？",
        expected={
            # 答案应含某个机构名（University / Institute / 大学 / 研究院 等）
            "contains_any": ["University", "Institute", "大学", "研究院", "School", "学院"],
            "min_tools": 1,
        },
        tags=["hard", "metadata_extraction"],
        notes="测试模型能否从 PDF 第一页正确提取作者机构",
    ),

    # ── HARD ④：跨论文方法对比（最难，需要读多篇 + 综合）─────────────
    EvalCase(
        id="hard_synthesis_methods_compare",
        input="三篇 NiFe 论文（cssc / ijhydene / catal8080328）分别用了什么催化剂的制备/合成方法？给出三篇的方法名称。",
        expected={
            # 期望提到至少 2 种合成方法（hydrothermal / electrodeposition / co-precipitation 等）
            "contains_any": [
                "hydrothermal", "水热", "electrodeposition", "电沉积",
                "co-precipitation", "共沉淀", "thermal", "热处理",
                "sol-gel", "deposition", "annealing", "煅烧",
            ],
            "min_tools": 3,
        },
        tags=["hard", "cross_paper", "method_synthesis"],
        notes="最难：跨 3 篇 + 找方法论部分（通常在中段）+ 综合表达。Pattern 02 的极限",
    ),

    # ── HARD ⑤：年份/时间元数据（需要看 PDF 内容里的发表信息）─────────
    EvalCase(
        id="hard_publication_year_range",
        input="我们藏书里这 5 篇论文，最早的发表于哪一年？最新的呢？",
        expected={
            # 数据集里有 2018（catal）和 2025（Yang / Nano Energy）
            "contains_all": ["2018", "2025"],
            "min_tools": 1,
        },
        tags=["hard", "metadata_extraction", "cross_paper"],
        notes="2018 catal8080328 最早、2025 Yang 和 Nano Energy 最新。需要从 preview 或 read 提取年份",
    ),
]
