# ADR-0002: chromadb as local vector DB

**Status**: accepted (2026-05-19)

## Context

Stage 2 引入 RAG 需要 vector DB。备选：

| 选项 | 类型 | 优点 | 缺点 |
|---|---|---|---|
| **chromadb** | 本地嵌入式 | 纯 Python、单文件持久化、API 极简 | 性能不如专业 DB（&gt;1M 向量后慢） |
| LanceDB | 本地嵌入式 | Rust 后端性能好、列式存储 | API 不如 chroma 直观、社区较小 |
| Qdrant | 服务端 | 企业级、丰富过滤 | 需起 docker、运维复杂 |
| Weaviate | 服务端 | 支持 graph query | 资源占用大 |
| Pinecone | SaaS | 零运维、scale 强 | 付费、数据上云 |
| FAISS | 内存库 | Facebook 出品、极快 | 不持久化、需自己包装 |

约束：
- 用户明确要求"都用本地"（隐私 + 离线）
- 学习项目，**设置成本必须最低**
- 5-1823 篇规模（最多 ~150k chunks）
- Mac 笔记本，CPU 跑

## Decision

选 **chromadb 1.5+**，PersistentClient 模式。

```python
client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_or_create_collection(name="papers", metadata={"hnsw:space": "cosine"})
```

## Consequences

### 正面
- **零运维**：无需 docker、无需启动服务，import 即用
- **持久化简单**：所有数据存在 `./chroma_db/` 目录下，可以打包带走
- **API 极简**：5 行代码完成 upsert + query
- **5-150k chunks 完全 hold 住**：在我们的规模下性能不是瓶颈
- **过滤能力够用**：`where={"paper_id": {"$in": [...]}}` 支持基本过滤
- **迁移容易**：if 真上 1M+，可以切到 LanceDB/Qdrant，`collection.query()` 接口几乎相同

### 负面
- **大规模性能**：100k+ chunks 后 query 延迟开始上升（500ms+）
- **单机绑定**：不支持多机分布式
- **没有专业 features**：比如 hybrid search（dense + sparse）需要自己实现

### 中性
- 默认带 telemetry，需要显式 `Settings(anonymized_telemetry=False)` 关掉
- 默认距离是 L2 不是 cosine，需要 metadata 里指定 `{"hnsw:space": "cosine"}`

## 否决其他备选的理由

- **LanceDB**：性能优势在我们规模下没体现，API 学习成本高
- **Qdrant/Weaviate**：需起服务，违反"本地零运维"约束
- **Pinecone**：付费 + 上云，不符合 user requirement
- **FAISS**：不持久化每次都要重新 build，开发效率低

## 升级触发条件

当出现以下信号时迁移到 LanceDB 或 Qdrant：
- chunks > 500k（接近 chromadb 性能边界）
- query p99 latency > 500ms
- 需要并发 query > 10 qps
- 多机部署需求
