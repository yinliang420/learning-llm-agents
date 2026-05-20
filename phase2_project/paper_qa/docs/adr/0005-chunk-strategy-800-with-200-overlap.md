# ADR-0005: Chunk strategy: 800 chars + 200 overlap, page-aware

**Status**: accepted (2026-05-19)

## Context

Stage 2 RAG 需要把 PDF 切成 chunks 才能 embed + 检索。切分策略影响：

- **检索粒度**：chunk 太大会包含无关信息（信噪比低），太小会丢上下文
- **embedding 质量**：MiniLM 模型 max 256 tokens（~1000 chars），超长会被截断
- **存储成本**：chunks 越多，DB 越大，query 越慢

备选 chunking 策略：

| 单位 | 大小 | 边界处理 | 优点 | 缺点 |
|---|---|---|---|---|
| 字符 | 800 + 200 overlap | 按页+窗口 | 简单、有效、可控 | 可能切断单词 |
| Token | 200 tokens + 50 overlap | 按 tokenizer | 精确控制 embedding 长度 | 慢、依赖 tokenizer |
| 句子 | 3-5 句 | 句号 / NLP 分句 | 语义完整 | 实现复杂、PDF 句号常残缺 |
| 段落 | 整段 | 双换行 | 自然语义单位 | PDF 段落结构经常乱 |
| 论文 section | 整 section | 标题检测 | 最语义化 | 论文格式各异，rule 难写 |
| 整页 | 整页 | 页边界 | 简单到不能再简单 | 超 embedding 上限被截 |

## Decision

**按页内 + 800 字符窗口 + 200 字符重叠**：

```python
def chunk_page_text(text: str, chunk_size: int = 800, overlap: int = 200) -> list[str]:
    text = " ".join(text.split())   # 压缩空白
    if len(text) <= chunk_size:
        return [text] if text else []
    chunks = []
    start = 0
    while start < len(text):
        chunks.append(text[start:start + chunk_size])
        if start + chunk_size >= len(text):
            break
        start += chunk_size - overlap
    return chunks
```

每个 chunk 还带 metadata：`{paper_id, page, chunk_idx}`。

## Consequences

### 正面
- **embedding 质量好**：800 字符 ≈ 200 tokens，安全在 MiniLM 256 token 上限内
- **边界缓解有效**：200 字符重叠 ≈ 1 句话，被切断的内容总有一个 chunk 完整包含
- **页边界保留**：每个 chunk 知道自己来自哪页，便于"在第 X 页找到"显示
- **实现极简**：30 行代码，无依赖
- **可重现**：纯字符级操作，与 PDF 提取质量解耦
- **数字平衡**：5 篇 → 412 chunks（avg 82 chunks/篇），DB 文件 ~50MB

### 负面
- **跨页内容丢边界**：一句话跨两页时，第一页末尾的 chunk 包含前半句，第二页开头的 chunk 包含后半句，但没有一个 chunk 包含完整这一句
- **会切断单词**："overpotential" 可能被切成 "overpoten" + "tial"。MiniLM 对部分单词的 embedding 仍然可用，但准确度略降
- **无语义边界感**：800 字符可能正好切到方程式中间，破坏语义

### 中性
- 800 / 200 是经验值。改成 1000/300 或 500/100 会有微小差别但量级不变
- 重叠率 25%（200/800）是 RAG 社区常见区间（10-30%）

## 否决其他备选的理由

- **按 token**：慢 3-5x，依赖 tokenizer 加载，对我们 800 字符目标的精确度收益不大
- **按句子**：PDF 经常缺句号（特别是公式 / 表格周围），分句不可靠
- **按段落**：PDF 段落检测对扫描版 / 图文混排经常失败
- **按 section**：论文格式差异大（一些有 "Methods" 标题，一些有 "2. Experimental"），rule-based detection 误差大
- **整页**：典型论文页 ~3000 字符，超 MiniLM 256 token 上限（~1000 chars），会被截断丢失后半页

## 未来改进的触发条件

✅ 现在够用。检索质量在 5 篇 + 15 cases 上验证 100% 通过。

🔧 当出现这些问题时考虑改：
- 跨页内容丢失导致 hard case 失败 → 试 1500 字符 + 400 overlap
- 公式 / 表格的检索质量明显差 → 考虑按 section 切，加专门的"表格 chunk"类型
- chunk 总数爆炸（&gt; 500k）→ 增大 chunk_size 减少总数（牺牲检索粒度）
- 跨论文 similarity 集中（已观察到）→ **不是 chunking 问题**，是检索策略问题，看 MMR 方案

## 数字调优经验值（备查）

| chunk_size | overlap | 检索粒度 | 适合 |
|---|---|---|---|
| 200-400 | 50-100 | 句级 | FAQ / 事实查询 |
| **500-1000** | **100-200** | **段落级** | **论文 QA、技术文档（我们）** |
| 1500-2000 | 300-400 | 多段 | 长文档综合理解 |
| 3000+ | 500+ | 章节级 | 完整章节理解 |
