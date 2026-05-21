"""Stage 2 检索器：把向量库包装成 agent 能调的 tool。

接口设计跟 Stage 1 的 search_in_paper 类似，但底层是语义检索（embedding 相似度），
不是字符串匹配。区别：
  - search_in_paper：必须输入精确关键词，找精确匹配
  - rag_search：输入自然语言意图，找语义相关
"""
from __future__ import annotations

from pathlib import Path

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

SCRIPT_DIR = Path(__file__).parent
DB_PATH = SCRIPT_DIR / "chroma_db"
COLLECTION_NAME = "papers"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# 单例 — 第一次 import 加载，之后复用
_encoder: SentenceTransformer | None = None
_collection = None


def _get_encoder() -> SentenceTransformer:
    global _encoder
    if _encoder is None:
        _encoder = SentenceTransformer(EMBEDDING_MODEL)
    return _encoder


def _get_collection():
    global _collection
    if _collection is None:
        client = chromadb.PersistentClient(
            path=str(DB_PATH),
            settings=Settings(anonymized_telemetry=False),
        )
        _collection = client.get_collection(name=COLLECTION_NAME)
    return _collection


def rag_search(query: str, paper_ids: list[str] | None = None, top_k: int = 5) -> dict:
    """语义检索向量库。

    Args:
        query:     自然语言查询（例如 "OER overpotential in mV"）
        paper_ids: 限定只在这些论文里搜（None = 全部论文）
        top_k:     返回最相关的 top_k 个 chunk

    Returns:
        {
          "found": True,
          "query": str,
          "match_count": int,
          "matches": [
            {"paper_id":..., "page":..., "text":..., "similarity": float},
            ...
          ]
        }
    """
    try:
        col = _get_collection()
    except Exception as e:
        return {"found": False, "error": f"DB not ready: {e}. Run indexer.py first."}

    # 把 query 转向量
    encoder = _get_encoder()
    query_vec = encoder.encode([query], show_progress_bar=False).tolist()[0]

    # 构造 chroma 的 where 过滤
    where = None
    if paper_ids:
        if len(paper_ids) == 1:
            where = {"paper_id": paper_ids[0]}
        else:
            where = {"paper_id": {"$in": paper_ids}}

    try:
        res = col.query(
            query_embeddings=[query_vec],
            n_results=top_k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
    except Exception as e:
        return {"found": False, "error": f"Query failed: {e}"}

    docs = res["documents"][0] if res["documents"] else []
    metas = res["metadatas"][0] if res["metadatas"] else []
    dists = res["distances"][0] if res["distances"] else []

    matches = []
    for doc, meta, dist in zip(docs, metas, dists):
        # 截断单个 chunk 到 400 字符，避免 messages 爆炸（学过的 State 外置 + 内容压缩思路）
        text_compact = doc[:400] + ("..." if len(doc) > 400 else "")
        matches.append({
            "paper_id": meta["paper_id"],
            "page": meta["page"],
            "text": text_compact,
            "similarity": round(1.0 - dist, 3),
        })

    return {
        "found": True,
        "query": query,
        "match_count": len(matches),
        "matches": matches,
        "filter_paper_ids": paper_ids,
        "hint": (
            "These are semantically-retrieved chunks. Use them as-is — "
            "do not re-search with rephrased queries unless similarity is very low."
        ),
    }


# 快速验证（python retriever.py 直接跑）
if __name__ == "__main__":
    print("=== Test 1: 简单查询 ===")
    r = rag_search("OER overpotential in mV at 10 mA/cm2", top_k=3)
    for m in r["matches"]:
        print(f"  • [{m['paper_id']} p{m['page']}, sim={m['similarity']}]")
        print(f"    {m['text'][:150]}...")
        print()

    print("=== Test 2: 限定 1 篇 ===")
    r = rag_search("synthesis method", paper_ids=["10.3390_catal8080328"], top_k=3)
    for m in r["matches"]:
        print(f"  • [{m['paper_id']} p{m['page']}, sim={m['similarity']}]")
        print(f"    {m['text'][:150]}...")
        print()

    print("=== Test 3: 跨 3 篇 NiFe ===")
    r = rag_search(
        "OER overpotential value",
        paper_ids=["10.1002_cssc.201901439", "10.1016_j.ijhydene.2020.03.192", "10.3390_catal8080328"],
        top_k=5,
    )
    print(f"  found {r['match_count']} chunks across {len(r['filter_paper_ids'])} papers")
    for m in r["matches"]:
        print(f"  • [{m['paper_id']} p{m['page']}, sim={m['similarity']}]")
        print(f"    {m['text'][:100]}...")
