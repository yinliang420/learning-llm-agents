# paper_qa Architecture

> 这份文档是给**开发者**看的。新人 30 分钟读完应该能理解整个项目的代码组织和数据流向。
> 决策的"为什么"看 `docs/adr/`。

---

## 1. 项目目标（north star）

让 PhD 学生能用自然语言问自己藏书里 1823 篇电催化论文。

**当前状态**：Stage 2，5 篇 RAG，准确率 100%。  
**下一步**：Stage 3，扩到 1823 篇 + 接外部搜索。

---

## 2. 顶层数据流

```
┌──────────┐    user question     ┌──────────────┐
│  User    │ ───────────────────► │  Agent loop  │
│  (CLI)   │                      │ (Pattern 02) │
└──────────┘                      └──────┬───────┘
                                         │ tool calls
                          ┌──────────────┼──────────────┐
                          ▼              ▼              ▼
                    ┌──────────┐   ┌──────────┐   ┌──────────┐
                    │list_     │   │ rag_     │   │ read_    │
                    │ papers   │   │ search   │   │ paper    │
                    └────┬─────┘   └────┬─────┘   └────┬─────┘
                         │              │              │
                         ▼              ▼              ▼
                    ┌──────────┐  ┌─────────────┐  ┌──────────┐
                    │ Papers/  │  │  chromadb   │  │ Papers/  │
                    │ dir scan │  │ vector DB   │  │ pdf read │
                    └──────────┘  └─────────────┘  └──────────┘
                                        ▲
                                        │ embed
                                  ┌─────┴──────┐
                                  │  Indexer   │  (run once)
                                  │ sentence-  │
                                  │ transformers│
                                  └────────────┘

  ┌────────────────┐              ┌─────────────┐
  │ Final answer   │ ──verify──► │  Verifier   │ (optional)
  │ + retrieved    │             │  LLM        │
  │ chunks         │             └─────────────┘
  └────────────────┘
```

---

## 3. 文件 / 模块 map

```
phase2_project/paper_qa/
├── papers/                    # 全量 1823 篇藏书（gitignored，太大）
├── papers_stage1/             # Stage 1 sampled 5 篇 (gitignored)
│
├── tools.py                   # Stage 1 工具：list_papers / read_paper / search_in_paper
├── agent.py                   # Stage 1 agent (Pattern 02)
├── eval_set.py                # 15 个 eval cases
├── run_eval.py                # Stage 1 + 模型对比 runner
│
├── stage2/
│   ├── indexer.py             # 一次性脚本：PDF → chunks → embed → chromadb
│   ├── retriever.py           # rag_search 工具
│   ├── agent_stage2.py        # Stage 2 agent (Pattern 02 + RAG)
│   ├── verify_citations.py    # 引用核对（Data Provenance）
│   ├── run_eval.py            # Stage 2 vs Stage 1 对比 runner
│   └── chroma_db/             # 本地向量库 (gitignored)
│
├── tests/                     # pytest unit tests（秒级跑）
│   ├── conftest.py            # fixtures (fake_pdf, fake_chromadb, ...)
│   ├── test_tools_stage1.py   # 11 个 test
│   └── test_stage2_components.py  # 19 个 test
│
├── docs/
│   └── adr/                   # Architecture Decision Records
│       ├── 0001-pattern-02-as-baseline.md
│       ├── 0002-chromadb-as-vector-db.md
│       ├── 0003-sentence-transformers-as-embedder.md
│       ├── 0004-sample-5-papers-first.md
│       ├── 0005-chunk-strategy-800-with-200-overlap.md
│       └── README.md
│
├── ARCHITECTURE.md            # ← 你正在看的
└── eval_*.json                # baseline + latest reports
```

**找代码的快捷规则**：
- 工具相关 → `tools.py` (Stage 1) 或 `stage2/retriever.py` (Stage 2)
- agent 主循环 → `agent.py` 或 `stage2/agent_stage2.py`
- 测试一个 case 失败 → `eval_set.py` 找 case 定义
- 修索引逻辑 → `stage2/indexer.py`
- 加新单测 → `tests/`

---

## 4. 关键设计决策概览

完整理由看对应的 ADR。这里只列结论：

| 决策 | 选择 | 关键理由 | ADR |
|---|---|---|---|
| Agent 模式 | Pattern 02 Tool-use Loop | 单 PDF QA 不需要 plan-execute | [0001](docs/adr/0001-pattern-02-as-baseline.md) |
| Vector DB | chromadb | 本地、零运维、Python 原生 | [0002](docs/adr/0002-chromadb-as-vector-db.md) |
| Embedding 模型 | sentence-transformers/all-MiniLM-L6-v2 | 完全本地、22MB、英文够用 | [0003](docs/adr/0003-sentence-transformers-as-embedder.md) |
| 起步规模 | 5 篇 sampled | 验证架构再扩，跳级失败率高 | [0004](docs/adr/0004-sample-5-papers-first.md) |
| Chunking | 800 字符 + 200 字符重叠 | 论文页友好、防边界丢失 | [0005](docs/adr/0005-chunk-strategy-800-with-200-overlap.md) |

---

## 5. 运行 / 开发命令速查

```bash
# 一次性索引（Stage 2 新文档要做）
uv run python stage2/indexer.py --reset

# 跑 Stage 1 eval
uv run python run_eval.py

# 跑 Stage 2 eval（对比 Stage 1 baseline）
uv run python -m stage2.run_eval

# 跑所有 unit tests（秒级）
uv run pytest tests/ -v

# 单独跑一组 test
uv run pytest tests/test_stage2_components.py::TestChunking -v

# 验证一个答案的引用
uv run python -m stage2.verify_citations    # smoke test
```

---

## 6. 数据流细节：Stage 2 一次完整调用

```
User asks "对比 SiC、铝的密度，谁更轻？"
   │
   ▼
agent_stage2.run(question)
   │
   ▼
[Round 1] call LLM with system + tools
   │
   ▼
LLM 决定：tool_calls = [rag_search("density of SiC and aluminium")]
   │
   ▼
agent 执行：retriever.rag_search(query, top_k=5)
   │
   ▼
retriever：
   1. encoder.encode([query]) → 384 维向量
   2. chromadb.query(query_vec, where={}) → top-5 chunks
   3. 每个 chunk 截到 400 字符 + similarity
   ▼
返回 {matches: [...], hint: "trust this result"}
   │
   ▼
[Round 2] call LLM with messages + tool result
   │
   ▼
LLM 综合：finish_reason="stop", text="铝更轻（2700 vs 3210 kg/m³）"
   │
   ▼
（可选）verify_citations(answer, retrieved_chunks)
   │
   ▼
最终返回 answer 给 user
```

每一步对应的代码：
- `agent.run()` → `stage2/agent_stage2.py:run`
- LLM call → `shared/llm.py:call`
- rag_search → `stage2/retriever.py:rag_search`
- verify → `stage2/verify_citations.py:verify_answer`

---

## 7. 已知技术债（应该读，避免重复发现）

| # | 问题 | 影响 | 修复优先级 |
|---|---|---|---|
| 1 | `shared/eval/__init__.py` 单文件 300+ 行混 6 个职责 | 难维护 | P1 |
| 2 | `run_eval.py` 有 SYSTEM_V1 / MODEL_OVERRIDE 死代码 | 配置混乱 | P0 |
| 3 | 3 处重复的 instrumented_agent 实现 | DRY 违反 | P1 |
| 4 | `verify_citations.extract_numeric_claims` dedup 太激进 | 相邻数字会丢 | P1 |
| 5 | 报告文件无统一命名/归档 | 久了不知道哪个是哪个 | P2 |
| 6 | Cross-paper 数字对比 Pattern 02 + RAG 也卡 | 需 Pattern 04 | P2 |

---

## 8. 下一阶段路线（Stage 3 设计）

目标：从 5 篇扩到 1823 篇 + 接外部 arxiv 搜索。

预期改动：
- `indexer.py`：必须支持增量 + 去重（DOI 匹配）
- 新增 `stage3/web_search.py`（接 Tavily / Semantic Scholar）
- agent 升级到 Pattern 04 Plan-Execute（处理 cross-paper 数字对比）
- 增加 ADR 记录新的决策

**预计代价**：1823 篇全索引 ~20 分钟（CPU embed），chromadb ~1GB。
