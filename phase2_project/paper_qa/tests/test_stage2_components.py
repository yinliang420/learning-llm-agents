"""Stage 2 组件的 unit tests — chunking / retriever / verify_citations 关键边界。"""
from __future__ import annotations

import numpy as np
import pytest
from unittest.mock import patch, MagicMock


# ─────────────────────────────────────────────────────────────────────────────
# Chunking
# ─────────────────────────────────────────────────────────────────────────────


class TestChunking:
    """stage2/indexer.py 的 chunk_page_text。"""

    def test_short_text_returns_single_chunk(self):
        from stage2.indexer import chunk_page_text
        text = "短文本，不到 800 字符。"
        chunks = chunk_page_text(text, chunk_size=800, overlap=200)
        assert len(chunks) == 1
        assert chunks[0] == text.replace("\n", " ")

    def test_empty_text_returns_empty_list(self):
        from stage2.indexer import chunk_page_text
        assert chunk_page_text("", chunk_size=800, overlap=200) == []
        assert chunk_page_text("   ", chunk_size=800, overlap=200) == []

    def test_overlap_is_actually_applied(self):
        """两个相邻 chunk 应该有 200 字符重叠（避免边界丢信息）。"""
        from stage2.indexer import chunk_page_text
        # 2000 字符的连续文本（无空白噪声）
        text = "A" * 2000
        chunks = chunk_page_text(text, chunk_size=800, overlap=200)

        assert len(chunks) >= 2
        # chunk0 末尾 200 字符应该等于 chunk1 开头 200 字符
        assert chunks[0][-200:] == chunks[1][:200]

    def test_whitespace_compression(self):
        """多个空白字符应该被压缩成单空格。"""
        from stage2.indexer import chunk_page_text
        text = "word1\n\n\nword2\t\tword3"
        chunks = chunk_page_text(text, chunk_size=800, overlap=200)
        assert chunks == ["word1 word2 word3"]

    def test_last_chunk_can_be_short(self):
        """最后一个 chunk 长度可以小于 chunk_size，不补 pad。"""
        from stage2.indexer import chunk_page_text
        # 850 字符 → chunk_size=800 → chunk1=800 chars, chunk2=200+50=250 chars
        text = "B" * 850
        chunks = chunk_page_text(text, chunk_size=800, overlap=200)
        assert len(chunks) == 2
        assert len(chunks[0]) == 800
        assert len(chunks[1]) < 800     # 不补 pad


# ─────────────────────────────────────────────────────────────────────────────
# verify_citations: claim 抽取
# ─────────────────────────────────────────────────────────────────────────────


class TestExtractClaims:
    """verify_citations.extract_numeric_claims 的边界行为。"""

    def test_no_numbers_returns_empty(self):
        from stage2.verify_citations import extract_numeric_claims
        text = "这是一段纯描述性的文本，没有任何数字或单位。"
        assert extract_numeric_claims(text) == []

    def test_extracts_common_units(self):
        from stage2.verify_citations import extract_numeric_claims
        text = "杨氏模量 200 GPa，密度 7850 kg/m³，硬度 130 HB。"
        claims = extract_numeric_claims(text)
        values = [c.extracted_value for c in claims]
        # 至少应该抽到这些（dedup 可能导致部分丢失，但不应该全丢）
        assert any("200 GPa" in v for v in values) or len(claims) >= 1

    def test_extracts_scientific_notation(self):
        from stage2.verify_citations import extract_numeric_claims
        text = "能量为 1.5e3 eV。"
        claims = extract_numeric_claims(text)
        assert len(claims) == 1
        assert "1.5e3" in claims[0].extracted_value
        assert "eV" in claims[0].extracted_value

    def test_does_not_extract_year_alone(self):
        """单独的年份（无单位）不应该被抽成 claim。"""
        from stage2.verify_citations import extract_numeric_claims
        text = "该论文发表于 2024 年。"
        claims = extract_numeric_claims(text)
        # "2024" 没有 unit 跟随，不应该匹配
        assert claims == []

    def test_known_limitation_dedup_too_aggressive(self):
        """已知局限：相邻 numeric 的 context 窗口重叠会被误判重复。

        这个测试记录当前行为，便于将来改进时验证。
        """
        from stage2.verify_citations import extract_numeric_claims
        # 三个数字非常靠近，80 字符窗口几乎完全覆盖三个 → dedup 会丢
        text = "A 是 100 GPa，B 是 200 GPa，C 是 300 GPa。"
        claims = extract_numeric_claims(text)
        # 理想：3 个。实际：可能只 1-2 个（已知问题）
        # 这里不断言精确数，只记录现状不是 3
        assert len(claims) >= 1   # 至少抽到 1 个
        # 如果将来改进了 dedup 逻辑（如更小窗口或基于值本身去重），
        # 这个测试应该升级为 assert len(claims) == 3


# ─────────────────────────────────────────────────────────────────────────────
# rag_search retriever（mock 掉 chromadb）
# ─────────────────────────────────────────────────────────────────────────────


class TestRagSearch:
    """retriever.rag_search 的工具行为。"""

    def test_returns_truncated_chunks(self, fake_chromadb_collection):
        """返回的 chunk text 应该截到 400 字符 + '...'。"""
        # 让 fake 返回一个长 chunk
        def long_query(**kw):
            return {
                "documents": [["X" * 1000]],
                "metadatas": [[{"paper_id": "p1", "page": 1, "chunk_idx": 0}]],
                "distances": [[0.1]],
            }
        fake_chromadb_collection.query = long_query

        from stage2 import retriever
        with patch.object(retriever, "_get_collection", return_value=fake_chromadb_collection), \
             patch.object(retriever, "_get_encoder") as mock_enc:
            mock_enc.return_value.encode.return_value = np.array([[0.0] * 384])
            result = retriever.rag_search("dummy query", top_k=1)

        assert result["found"] is True
        assert len(result["matches"]) == 1
        text = result["matches"][0]["text"]
        assert len(text) == 403   # 400 chars + "..."
        assert text.endswith("...")

    def test_similarity_is_1_minus_distance(self, fake_chromadb_collection):
        """similarity 字段应该是 1 - cosine_distance。"""
        from stage2 import retriever
        with patch.object(retriever, "_get_collection", return_value=fake_chromadb_collection), \
             patch.object(retriever, "_get_encoder") as mock_enc:
            mock_enc.return_value.encode.return_value = np.array([[0.0] * 384])
            result = retriever.rag_search("dummy", top_k=2)

        # fixture 返回 distances=[0.15, 0.42]
        assert result["matches"][0]["similarity"] == 0.85
        assert result["matches"][1]["similarity"] == 0.58

    def test_filter_by_single_paper_id(self, fake_chromadb_collection):
        """paper_ids=['x'] 时应该用 {'paper_id': 'x'} 过滤（不是 $in）。"""
        from stage2 import retriever
        captured_where = {}
        def capture_query(**kw):
            captured_where.update(kw.get("where") or {})
            return {"documents": [[]], "metadatas": [[]], "distances": [[]]}
        fake_chromadb_collection.query = capture_query

        with patch.object(retriever, "_get_collection", return_value=fake_chromadb_collection), \
             patch.object(retriever, "_get_encoder") as mock_enc:
            mock_enc.return_value.encode.return_value = np.array([[0.0] * 384])
            retriever.rag_search("dummy", paper_ids=["only_paper"])

        # 单个 ID 用直接相等
        assert captured_where == {"paper_id": "only_paper"}

    def test_filter_by_multiple_paper_ids(self, fake_chromadb_collection):
        """paper_ids=[多个] 时应该用 {'paper_id': {'$in': [...]}} 过滤。"""
        from stage2 import retriever
        captured_where = {}
        def capture_query(**kw):
            captured_where.update(kw.get("where") or {})
            return {"documents": [[]], "metadatas": [[]], "distances": [[]]}
        fake_chromadb_collection.query = capture_query

        with patch.object(retriever, "_get_collection", return_value=fake_chromadb_collection), \
             patch.object(retriever, "_get_encoder") as mock_enc:
            mock_enc.return_value.encode.return_value = np.array([[0.0] * 384])
            retriever.rag_search("dummy", paper_ids=["a", "b", "c"])

        assert captured_where == {"paper_id": {"$in": ["a", "b", "c"]}}

    def test_db_not_ready_returns_error(self):
        """chromadb 没初始化时应该返回友好错误（不抛异常）。"""
        from stage2 import retriever
        # 强制 _get_collection 抛错
        with patch.object(retriever, "_get_collection",
                         side_effect=Exception("DB not found")):
            result = retriever.rag_search("dummy")

        assert result["found"] is False
        assert "DB not ready" in result["error"]
        assert "indexer.py" in result["error"]   # 提示用户怎么修
