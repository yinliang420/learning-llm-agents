"""
Pattern 05: Reflection / Evaluator-Optimizer
=============================================

核心思路：生成 → 评估 → 修改 → 重复
关键原则：Evaluator 必须和 Generator 用不同 prompt（否则自我审查等于没有）

踩坑预警（demo 里有意展示）：
  1. 反思越改越错：原答案是对的，反思反而改坏了
  2. 橡皮图章：自我评估总是通过，反思等于没有
  3. 无限循环：没有明确停止条件

MAX_ROUNDS = 2  ← 学习阶段限制轮数，看清楚每轮在干什么
"""

from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from shared.llm import call

DB = {
    "steel":     {"Young's modulus": (200, "GPa"), "density": (7850, "kg/m³"), "melting point": (1370, "°C"), "hardness": (130,  "HB")},
    "aluminium": {"Young's modulus": (69,  "GPa"), "density": (2700, "kg/m³"), "melting point": (660,  "°C"), "hardness": (25,   "HB")},
    "SiC":       {"Young's modulus": (410, "GPa"), "density": (3210, "kg/m³"), "melting point": (2730, "°C"), "hardness": (2500, "HV")},
    "copper":    {"Young's modulus": (110, "GPa"), "density": (8960, "kg/m³"), "melting point": (1085, "°C"), "hardness": (35,   "HB")},
    "titanium":  {"Young's modulus": (116, "GPa"), "density": (4500, "kg/m³"), "melting point": (1668, "°C"), "hardness": (70,   "HB")},
}

DATA_CONTEXT = """Materials database:
""" + "\n".join(
    f"  {mat}: " + ", ".join(f"{p}={v}{u}" for p, (v, u) in props.items())
    for mat, props in DB.items()
)

MAX_ROUNDS = 2
QUALITY_THRESHOLD = 8  # 满分 10 分

# ── Generator ────────────────────────────────────────────────────────────────

GENERATOR_SYSTEM = f"""You are a materials science analyst.
Use the following data to answer questions accurately and concisely.

{DATA_CONTEXT}"""

def generate(question: str, feedback: str = "") -> str:
    prompt = question
    if feedback:
        prompt += f"\n\n[Previous feedback to address]: {feedback}"
    r = call([{"role": "user", "content": prompt}], system=GENERATOR_SYSTEM, max_tokens=512)
    return r.text

# ── Evaluator（关键：和 Generator 用完全不同的 prompt）────────────────────────

EVALUATOR_SYSTEM = f"""You are a strict technical reviewer for materials science content.
Ground truth data:
{DATA_CONTEXT}

Evaluate the answer on:
  1. Factual accuracy (values match the database)
  2. Completeness (addresses all parts of the question)
  3. Clarity (well-structured and concise)

Respond in this exact format:
SCORE: [0-10]
ISSUES: [specific problems found, or "none"]
SUGGESTION: [one concrete improvement, or "none"]"""

def evaluate(question: str, answer: str) -> tuple[int, str, str]:
    prompt = f"Question: {question}\n\nAnswer to evaluate:\n{answer}"
    r = call([{"role": "user", "content": prompt}], system=EVALUATOR_SYSTEM, max_tokens=256)
    text = r.text
    score = 5
    issues = "could not parse"
    suggestion = "none"
    for line in text.split("\n"):
        if line.startswith("SCORE:"):
            try: score = int(line.split(":")[1].strip())
            except: pass
        elif line.startswith("ISSUES:"):
            issues = line.split(":", 1)[1].strip()
        elif line.startswith("SUGGESTION:"):
            suggestion = line.split(":", 1)[1].strip()
    return score, issues, suggestion

# ── Reflection loop ───────────────────────────────────────────────────────────

def run(question: str) -> str:
    answer = generate(question)
    print(f"\n[Round 0 — Initial answer]\n{answer}")

    for round_num in range(1, MAX_ROUNDS + 1):
        score, issues, suggestion = evaluate(question, answer)
        print(f"\n[Evaluator — Round {round_num}]")
        print(f"  Score: {score}/10")
        print(f"  Issues: {issues}")
        print(f"  Suggestion: {suggestion}")

        if score >= QUALITY_THRESHOLD:
            print(f"  ✓ Quality threshold reached, stopping.")
            break

        # 生成改进版本
        answer = generate(question, feedback=f"Issues: {issues}. Suggestion: {suggestion}")
        print(f"\n[Round {round_num} — Revised answer]\n{answer}")

    return answer

if __name__ == "__main__":
    q = "给工程师写一份简短的材料选型建议：在需要同时考虑轻量和高刚度的场景下，推荐哪种材料？请列出你的数据支撑。"
    print(f"Q: {q}")
    print(f"\n最终答案:\n{run(q)}")
