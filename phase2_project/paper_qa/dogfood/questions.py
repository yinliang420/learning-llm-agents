"""10 个真实 PhD 级别问题，故意挑战 paper_qa 的边界。

设计原则（每个问题对应一个真实研究场景）：
  1. cross-paper synthesis（综合多篇）
  2. mechanism reasoning（机理推理，不只是 lookup）
  3. quantitative ranking（定量排序，跨论文）
  4. critical assessment（批判性判断，需要 agent 给观点）
  5. specific number deep-dig（精确数字 + 上下文）
  6. methodology comparison（方法学对比）
  7. application recommendation（应用建议）
  8. authorship / origin（元数据延伸）
  9. novelty assessment（新颖性判断）
  10. stability / durability（稳定性专项）

这些问题里至少一半会暴露 Stage 2 的局限。这正是 dogfood 的目的。
"""
from dataclasses import dataclass


@dataclass
class DogfoodQuestion:
    id: str
    question: str
    why_realistic: str
    expected_pain_point: str   # 我们预期会怎么失败


QUESTIONS: list[DogfoodQuestion] = [

    # ─── 1: cross-paper 机理对比 ─────────────────────────────────────────
    DogfoodQuestion(
        id="mechanism_cross_paper",
        question=(
            "在这几篇论文里，NiFe 基催化剂在 OER 过程中的活性位点机理有什么共识？"
            "有没有论文之间相互矛盾的解释？"
        ),
        why_realistic="写综述时必问 — 不同 group 对同一类材料的机理解释往往不同",
        expected_pain_point="cross-paper 综合 + 需要识别'矛盾'这个抽象概念",
    ),

    # ─── 2: 定量排序 + 条件归一化 ───────────────────────────────────────
    DogfoodQuestion(
        id="overpotential_ranking_normalized",
        question=(
            "把所有论文里报告的 OER 催化剂按 10 mA/cm² 下的 overpotential 排序，"
            "如果论文只报告了其他电流密度（如 100 mA/cm²），明确说明，不要硬比较。"
        ),
        why_realistic="选材料做下一步实验时的关键决策，要求 agent 区分'可比'和'不可比'",
        expected_pain_point="我们已知的 Pattern 02 + RAG 极限：电流密度不一致问题",
    ),

    # ─── 3: 单篇深度 + 特定参数 ─────────────────────────────────────────
    DogfoodQuestion(
        id="iridium_tafel_specific",
        question="Yang 那篇 Iridium 钙钛矿论文里，他们报告的 Tafel 斜率是多少？是 in-situ 测的还是 LSV 推算的？",
        why_realistic="审稿时常问 — Tafel 斜率的物理含义取决于测量方式",
        expected_pain_point="需要找出具体数值 + 实验方法学细节",
    ),

    # ─── 4: 合成方法对比（带工艺细节）───────────────────────────────────
    DogfoodQuestion(
        id="synthesis_methods_detail",
        question=(
            "三篇 NiFe 论文用了什么合成方法？给出每篇的：(1) 前驱体；"
            "(2) 反应温度和时间；(3) 后处理（如有）。要具体不要泛泛而谈。"
        ),
        why_realistic="尝试复现别人工作时要的细节，agent 要能从 experimental section 提取",
        expected_pain_point="多步信息抽取 + 跨论文整理成对比表",
    ),

    # ─── 5: 稳定性 / durability 对比 ────────────────────────────────────
    DogfoodQuestion(
        id="stability_comparison",
        question=(
            "这几篇论文都测了催化剂的稳定性吗？测试时长分别是多少小时？"
            "稳定性测试条件（电流密度 / 电解液）有什么不同？"
        ),
        why_realistic="工业应用前必看，稳定性测试条件不一致是常见 pitfall",
        expected_pain_point="多维度跨论文比较 + 部分信息可能不在 RAG top-k 里",
    ),

    # ─── 6: 应用判断（agent 给观点）──────────────────────────────────────
    DogfoodQuestion(
        id="application_recommendation",
        question=(
            "如果要做工业规模碱性水电解（10 A/cm²，5000 小时寿命），"
            "这几篇论文里哪种催化剂最有潜力？为什么？哪些数据不足以判断？"
        ),
        why_realistic="毕业论文 discussion 章节风格 — 需要 agent 综合判断 + 承认数据缺口",
        expected_pain_point="需要 critical thinking 而不是简单 lookup，agent 容易过度自信",
    ),

    # ─── 7: 元数据延伸（机构归属）─────────────────────────────────────
    DogfoodQuestion(
        id="institutional_origins",
        question="这 5 篇论文分别来自哪些国家 / 研究机构？有没有跨机构合作？",
        why_realistic="判断研究方向的全球分布，找潜在合作者",
        expected_pain_point="作者机构信息通常在首页，但格式各异（中英文混排）",
    ),

    # ─── 8: 新颖性判断（agent 抽象推理）─────────────────────────────────
    DogfoodQuestion(
        id="most_novel_finding",
        question=(
            "在这 5 篇论文里，你认为最有新颖性的科学发现是什么？"
            "为什么这个发现重要？（要给具体理由，不能是'XX 性能好'这种废话）"
        ),
        why_realistic="组会汇报 / paper club 风格 — 需要 agent 跳出'摘要复述'层面",
        expected_pain_point="主观判断 + 抽象层级，agent 大概率给敷衍答案",
    ),

    # ─── 9: 表征技术对比（方法学）───────────────────────────────────────
    DogfoodQuestion(
        id="characterization_techniques",
        question=(
            "这几篇论文都用了哪些 in-situ / operando 表征技术（如 in-situ XAS、operando Raman）？"
            "哪几篇用得最深入？只列 ex-situ 表征的不算。"
        ),
        why_realistic="判断研究深度，in-situ 是高水平工作的标志",
        expected_pain_point="需要识别'in-situ'这个特定属性 + 跨论文统计",
    ),

    # ─── 10: 反例 / 局限性 ──────────────────────────────────────────────
    DogfoodQuestion(
        id="limitations_admitted",
        question=(
            "这几篇论文里，作者自己承认的局限性 / 未解决的问题是什么？"
            "（看 conclusion / outlook 部分）"
        ),
        why_realistic="找研究 gap 写 proposal — 别人的局限就是你的机会",
        expected_pain_point="conclusion 通常在论文末尾，RAG chunking 是否能找到？",
    ),
]
