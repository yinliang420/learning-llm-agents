"""引用核对：agent 答案里的事实是否真的由 retrieved chunks 支持。

这是研究 agent 的命门。Generator LLM 可能在综合时漂移、补充训练记忆里的数字，
导致答案看起来对，但 source 根本没说。Verifier 是独立 LLM call，专门反查。

设计原则：
  1. Verifier 用不同的 SYSTEM prompt（不能让它"宽容自己")
  2. Verifier 只看 source chunks，不靠任何外部知识
  3. 把 claim 拆细：数字 + 单位 + 主体（哪个材料/方法）
  4. 输出结构化结果，便于后续处理（标记、删除、警告）

用法：
    from stage2.verify_citations import verify_answer
    result = verify_answer(answer_text, retrieved_chunks)
    print(f"Support rate: {result['support_rate']:.0%}")
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from shared.llm import call


# ─────────────────────────────────────────────────────────────────────────────
# 数据结构
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class Claim:
    """一个待核对的事实陈述。"""
    text: str                            # 原文片段，如 "SiC 的杨氏模量为 410 GPa"
    claim_type: str                      # "numeric" / "categorical" / "method"
    extracted_value: str | None = None   # 提取的核心值（数字+单位 或 类别）


@dataclass
class Verification:
    """单个 claim 的核对结果。"""
    claim: Claim
    supported: bool                       # 真/假
    confidence: float                     # 0-1，verifier LLM 给的置信度
    reasoning: str                        # verifier 的推理（便于审计）
    relevant_chunks: list[dict] = field(default_factory=list)   # 哪些 chunks 支持


@dataclass
class VerificationReport:
    """整个答案的核对报告。"""
    original_answer: str
    claims: list[Verification]
    support_rate: float                   # 通过的 claim 比例
    cost_usd: float

    @property
    def unsupported(self) -> list[Verification]:
        return [c for c in self.claims if not c.supported]

    def annotated_answer(self) -> str:
        """生成带标记的答案，不支持的 claim 加 [UNVERIFIED]。"""
        result = self.original_answer
        for v in self.unsupported:
            # 简化：在 claim 文本后插入标记
            result = result.replace(v.claim.text, f"{v.claim.text} [UNVERIFIED]")
        return result


# ─────────────────────────────────────────────────────────────────────────────
# Step 1: 抽 claim
# ─────────────────────────────────────────────────────────────────────────────


# 数字+单位的正则（覆盖电催化领域常见单位）
# 例：410 GPa, 7850 kg/m³, 25 °C, 190 mV, 10 mA cm-2, 0.95 eV
NUMERIC_PATTERN = re.compile(
    r"""
    (?P<value>\d+(?:[.,]\d+)?(?:[eE][+-]?\d+)?)   # 数字（含小数、科学计数）
    \s?
    (?P<unit>
        GPa|MPa|kPa|Pa                              # 力学
       |kg/m³|kg/m\^3|g/cm³|g/cm\^3                # 密度
       |°C|°F|K\b|kelvin                          # 温度
       |mV|V\b|volts?                              # 电位
       |mA\s?cm[⁻\-−]?2|mA/cm²|mA/cm\^2           # 电流密度
       |HV|HB|HRC|HRA                              # 硬度
       |nm|µm|um|μm|mm|cm|m\b                     # 长度
       |%|wt%|at%                                  # 百分比
       |eV|kJ/mol|kcal/mol                         # 能量
       |Hz|kHz|MHz|GHz                             # 频率
       |倍|times                                    # 倍数
    )
    """,
    re.VERBOSE | re.IGNORECASE,
)


def extract_numeric_claims(text: str, window_chars: int = 80) -> list[Claim]:
    """从答案文本里抽出所有数字 + 上下文 → numeric claim。

    window_chars: 数字前后取多少字符做 claim 上下文（用于 verifier 理解 claim 在说什么）
    """
    claims: list[Claim] = []
    seen: set[str] = set()                # 去重

    for match in NUMERIC_PATTERN.finditer(text):
        # 取前后窗口
        start = max(0, match.start() - window_chars)
        end = min(len(text), match.end() + window_chars)
        context = text[start:end].strip()
        # 压缩空白便于去重
        context_norm = " ".join(context.split())

        if context_norm in seen:
            continue
        seen.add(context_norm)

        value = f"{match.group('value')} {match.group('unit')}".strip()
        claims.append(Claim(
            text=context_norm,
            claim_type="numeric",
            extracted_value=value,
        ))

    return claims


# ─────────────────────────────────────────────────────────────────────────────
# Step 2: verifier LLM
# ─────────────────────────────────────────────────────────────────────────────


VERIFIER_SYSTEM = """You are a STRICT fact-checker for scientific paper claims.

Your job: given a claim and source chunks retrieved from papers,
judge whether the source chunks ACTUALLY SUPPORT the claim.

RULES (strict — do not be lenient):
1. The claim must be DIRECTLY supported by text in the chunks.
   "Implied" or "could be inferred" → NOT SUPPORTED.
2. Numeric values must match exactly (allow ±5% rounding for measurements).
3. If a chunk says a similar but different value (e.g., chunk says 200 GPa,
   claim says 210 GPa) → NOT SUPPORTED.
4. If chunks contain related context but not the specific claim → NOT SUPPORTED.
5. Hallucinated paper-IDs or page references → NOT SUPPORTED.

Output STRICT JSON, no other text:
{
  "supported": true | false,
  "confidence": 0.0 - 1.0,
  "reasoning": "one-sentence why",
  "supporting_chunk_ids": [list of chunk_ids that support, or empty list]
}"""


def verify_one_claim(claim: Claim, candidate_chunks: list[dict]) -> Verification:
    """对单个 claim 调一次 verifier LLM。

    candidate_chunks: 已检索回来的 chunks，每个含 {paper_id, page, text, ...}
    返回 Verification 对象。
    """
    # 构造 verifier 提示
    chunks_repr = "\n\n".join(
        f"[chunk_id={i}] paper={c['paper_id']} p{c['page']}\n{c['text']}"
        for i, c in enumerate(candidate_chunks)
    )

    prompt = f"""CLAIM TO VERIFY:
{claim.text}
{f"(Extracted value: {claim.extracted_value})" if claim.extracted_value else ""}

SOURCE CHUNKS:
{chunks_repr}

Strictly evaluate whether the claim is supported.
Output JSON only."""

    response = call(
        messages=[{"role": "user", "content": prompt}],
        system=VERIFIER_SYSTEM,
        max_tokens=300,
    )

    # 解析 JSON 输出（防止模型乱说话）
    try:
        text = response.text.strip()
        # 容错：模型有时包 ```json ... ```
        if "```" in text:
            text = text.split("```")[1].lstrip("json").strip()
        parsed = json.loads(text)
        supported = bool(parsed.get("supported", False))
        confidence = float(parsed.get("confidence", 0.0))
        reasoning = parsed.get("reasoning", "")
        supporting_ids = parsed.get("supporting_chunk_ids", [])
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        # Verifier 输出不合规 → 保守判 NOT SUPPORTED
        supported = False
        confidence = 0.0
        reasoning = f"[verifier output parse error: {e}]"
        supporting_ids = []

    relevant = [candidate_chunks[i] for i in supporting_ids
                if isinstance(i, int) and 0 <= i < len(candidate_chunks)]

    return Verification(
        claim=claim,
        supported=supported,
        confidence=confidence,
        reasoning=reasoning,
        relevant_chunks=relevant,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Step 3: 完整流程入口
# ─────────────────────────────────────────────────────────────────────────────


def verify_answer(
    answer: str,
    retrieved_chunks: list[dict],
    max_claims_to_verify: int = 10,
) -> VerificationReport:
    """对完整答案做 provenance 核对。

    Args:
        answer: agent 给出的最终文本答案
        retrieved_chunks: 生成答案时检索回的 chunks（即 rag_search 的所有结果）
        max_claims_to_verify: 一次最多核对几个 claim（防 verifier 调用爆炸）

    Returns:
        VerificationReport，含 support_rate / 详细 verification list / cost
    """
    # 1) 抽 claim
    all_claims = extract_numeric_claims(answer)
    if not all_claims:
        return VerificationReport(
            original_answer=answer,
            claims=[],
            support_rate=1.0,      # 没有 claim → 视为 100% 支持
            cost_usd=0.0,
        )

    # 限制最多核对几个（防爆）
    claims_to_check = all_claims[:max_claims_to_verify]

    # 2) 逐个 verify
    verifications: list[Verification] = []
    total_cost = 0.0
    for claim in claims_to_check:
        # 这里简化：把所有 retrieved_chunks 都给 verifier 看
        # 生产版应该用 embedding 找最相关的 top-k
        v = verify_one_claim(claim, retrieved_chunks)
        verifications.append(v)
        # 注：verify_one_claim 内部 call() 没有暴露 cost 出来
        # 真要追踪，需要改 verify_one_claim 接收 cost callback
        # 这里简化为按平均估算
        total_cost += 0.0005   # 估算每次 verifier ~$0.0005

    # 3) 汇总
    supported_count = sum(1 for v in verifications if v.supported)
    support_rate = supported_count / len(verifications)

    return VerificationReport(
        original_answer=answer,
        claims=verifications,
        support_rate=support_rate,
        cost_usd=total_cost,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Demo / CLI
# ─────────────────────────────────────────────────────────────────────────────


def _print_report(report: VerificationReport) -> None:
    print(f"\n{'═' * 64}")
    print(f"  Verification Report")
    print(f"  Support rate: {report.support_rate:.1%}  ({len(report.claims)} claims checked)")
    print(f"  Estimated cost: ~${report.cost_usd:.4f}")
    print(f"{'═' * 64}\n")

    for i, v in enumerate(report.claims, 1):
        mark = "✓" if v.supported else "✗"
        print(f"  [{i}] {mark} {v.claim.extracted_value or v.claim.text[:60]}")
        print(f"      conf={v.confidence:.2f}  reasoning: {v.reasoning[:120]}")
        if v.relevant_chunks:
            print(f"      supporting chunks: {len(v.relevant_chunks)}")
        print()

    if report.unsupported:
        print(f"\n  ⚠ {len(report.unsupported)} unsupported claims found.")
        print(f"\n  Annotated answer (with [UNVERIFIED] tags):")
        print(f"  {report.annotated_answer()[:500]}...")
    print(f"{'═' * 64}\n")


if __name__ == "__main__":
    # 快速 smoke test：构造一个混合 (supported + fabricated) 的答案
    fake_answer = (
        "根据查询结果，SiC 的杨氏模量约为 410 GPa，密度为 3210 kg/m³。"
        "钢的密度大约是 7850 kg/m³，硬度约为 130 HB。"
        "另一个发现是钨的熔点是 3422 °C，远高于其他材料。"   # 这一句是 fabricated（DB 里没钨）
    )

    fake_chunks = [
        {"paper_id": "10.3390_catal8080328", "page": 1,
         "text": "SiC (silicon carbide) has a Young's modulus of approximately 410 GPa and density of 3210 kg/m³."},
        {"paper_id": "10.1002_cssc.201901439", "page": 2,
         "text": "Steel typically has a density of 7850 kg/m³ and Brinell hardness of 130 HB."},
    ]

    report = verify_answer(fake_answer, fake_chunks)
    _print_report(report)
