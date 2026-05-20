# ADR-0003: sentence-transformers/all-MiniLM-L6-v2 as embedding model

**Status**: accepted (2026-05-19)

## Context

Stage 2 RAG 需要 embedding 模型。备选：

| 选项 | 大小 | 维度 | 部署 | 成本 |
|---|---|---|---|---|
| **sentence-transformers/all-MiniLM-L6-v2** | 22 MB | 384 | 本地 CPU | $0 |
| BAAI/bge-small-zh-v1.5 | 95 MB | 512 | 本地 CPU | $0 |
| nomic-embed-text | 540 MB | 768 | 本地 CPU | $0 |
| OpenAI text-embedding-3-small | — | 1536 | API | $0.02/1M tokens |
| DashScope text-embedding-v3 | — | 1024 | API | 免费 tier |
| Voyage voyage-3 | — | 1024 | API | 付费 |

约束：
- 用户明确要求"都用本地"
- 论文是英文（不需要中文优化模型）
- Mac CPU，没有 GPU
- 1823 篇 × 80 chunks ≈ 150k embedding，要在合理时间内完成

## Decision

选 **sentence-transformers/all-MiniLM-L6-v2**。

```python
from sentence_transformers import SentenceTransformer
encoder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
embeddings = encoder.encode(texts, show_progress_bar=False, convert_to_numpy=True)
```

## Consequences

### 正面
- **完全本地**：22MB 模型首次自动下载，之后离线工作
- **CPU 速度可接受**：单条 ~50ms，批量 (batch=64) ~3ms/条
- **存储占用低**：384 维 × 4 bytes = 1.5KB/chunk，150k chunks ≈ 220MB
- **chromadb 兼容好**：默认配置即可工作
- **社区成熟**：sentence-transformers 是事实标准，bug 少，文档全

### 负面
- **仅英文**：中文论文需要换模型（如 BAAI/bge）
- **维度小**：384 维相比 OpenAI 的 1536 维信息密度较低
- **语义理解略弱**：对长 query 或专业术语不如更大的模型
- **首次下载需联网**：~22MB，几秒钟，但完全离线环境会受影响

### 中性
- 在我们 paper_qa 场景，质量已经够：测试中 NiFe / OER / overpotential 等专业词检索正确
- 升级到 BGE / nomic-embed 需要重新 embed 所有 chunks（~20 分钟一次性成本）

## 否决其他备选的理由

- **OpenAI text-embedding-3-small**：质量最好但**违反"本地"约束** + 付费
- **DashScope embedding**：本质还是 cloud API + 数据上云
- **BGE-zh**：我们论文是英文，中文优化白浪费
- **nomic-embed-text**：540MB 模型，对学习项目来说"重了"。等真有质量问题再换
- **FAISS-IVF + 自训 embedding**：完全过度工程

## 已知局限的应对

**问题**：跨 3 篇 NiFe 论文搜 OER 时，cosine similarity 容易集中在某一篇（top-5 都来自同一篇）。

**根因**：MiniLM 模型对论文细节差异分辨不强，相同主题不同来源 chunks 的 embedding 距离很近。

**应对（按代价递增）**：
1. 加 MMR（max marginal relevance）重排 — **代价小、效果可观**（推荐先尝试）
2. 改用 per-paper top-k 检索 — 简单粗暴，结构性解决
3. 换更大 embedding（如 BGE-large 1024 维）— 重新索引 ~30 分钟
4. 微调 embedding（domain adaptation）— 大工程
