# ADR-0004: Sample 5 papers first before scaling to full corpus

**Status**: accepted (2026-05-18)

## Context

用户提供了 1823 篇电催化论文藏书（7.4GB）。Stage 1 的合理 corpus 大小？

备选：
- 全部 1823 篇
- 中等子集 50-200 篇
- 小样本 5-10 篇

考虑因素：
- Indexer 速度（每篇 ~1.5s embedding，1823 篇 ~45 分钟）
- chromadb 文件大小（150k chunks ~ 1GB）
- 调试反馈循环时间（出 bug 重跑成本）
- 测试可信度（5 篇人可以全读，1823 篇不可能）

## Decision

**Stage 1 用 5 篇随机采样**（`random.seed(42)`，可重现）。

```python
import random
random.seed(42)
sample = random.sample(all_pdfs, 5)
```

后续渐进式扩规模：
- Stage 1: 5 篇（验证<strong>架构</strong>正确）
- Stage 2: 50-100 篇（验证<strong>检索质量</strong>）
- Stage 3: 1823 篇全量（验证<strong>性能与成本</strong>）

## Consequences

### 正面
- **调试反馈快**：indexer 跑完 30 秒，可以反复改 chunk 策略对比
- **eval set 设计有据**：5 篇 PDF 我可以全读，知道里面有什么，写 expected 准确
- **第一次架构错误的代价小**：发现 chunk 策略不对，重 build 30 秒 vs 45 分钟
- **测试可信度高**：手工核对 10 个问题的答案，能 100% 确认是否准确

### 负面
- **检索质量信号弱**：5 篇 chunks 太少，rag_search 几乎总能命中正确答案，掩盖检索质量问题
- **跨论文场景不丰富**：5 篇里 3 篇 NiFe，cross-paper 测试单一
- **现实使用场景 mismatch**：真实用户用 1823 篇时遇到的问题（如 chunks 重叠、检索噪声）Stage 1 测不出来

### 中性
- `random.seed(42)` 保证可重现，但也意味着采样固定。改了 seed 可能采到完全不同主题的 5 篇

## 触发扩规模的信号

✅ Stage 1 → Stage 2 已触发：
- 所有 happy path eval 通过
- 跨 3 篇 NiFe 的极限 case 暴露了 Pattern 02 + search_in_paper 的瓶颈
- → 决定上 RAG（Stage 2）

⏳ Stage 2 → Stage 3 触发条件（未达）：
- Stage 2 在 5-50 篇上 eval 稳定通过
- 加 MMR 解决了 cross-paper similarity 集中问题
- agent 在真实研究问题上有 dogfood 使用

## 否决其他备选的理由

- **直接全量 1823 篇**：
  - 第一次架构肯定不对，每次重 build 45 分钟，反馈循环慢一个数量级
  - 写 eval 时不知道里面有什么，写不出有意义的 expected 值
  - chromadb 1GB 文件，git LFS 都嫌大
- **50-100 篇**：
  - 太多读不过来，写 expected 全靠盲猜
  - 但又不够多到必须用 RAG，处于尴尬中间状态
  - 跳过这一档，直接从 5 一跃到 Stage 2 的 50

## 跳级失败的反例（要避免的反模式）

很多人看 Deep Research 的 demo 就想直接做 1000+ 篇的研究 agent。结果：
- Indexer 跑了 1 小时发现 chunking 策略不对，整个重来
- Eval 写不出来，靠人工 spot check，没有量化指标
- Agent 在某些问题上失败，但 corpus 太大不知道是检索问题还是 prompt 问题
- 项目通常死在第 3 周

**5 → 50 → 1823 的渐进路线代价低，反馈快**，比一上来全量便宜 10x。
