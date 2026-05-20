"""pytest 公共 fixtures。

设计原则：
  - 所有外部依赖（PdfReader / chromadb / encoder / LLM）都 mock 掉
  - 单测应该秒级跑完，不能依赖网络
  - fixtures 提供干净的隔离环境
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# 让测试能 import paper_qa 模块
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "stage2"))


@pytest.fixture
def fake_pdf_pages():
    """构造一组假的 PDF 页对象（模拟 PdfReader.pages）。"""
    def make_page(text: str):
        page = MagicMock()
        page.extract_text.return_value = text
        return page
    return make_page


@pytest.fixture
def temp_papers_dir(tmp_path):
    """临时 papers 目录，单测结束后自动清理。"""
    d = tmp_path / "papers"
    d.mkdir()
    return d


@pytest.fixture
def fake_chromadb_collection():
    """一个 in-memory 假 chromadb collection。"""
    col = MagicMock()

    def fake_query(query_embeddings, n_results, where=None, include=None):
        # 返回 2 个假 chunks 模拟检索结果
        return {
            "documents": [["chunk text 1 with overpotential 190 mV", "chunk text 2 about NiFe synthesis"]],
            "metadatas": [[
                {"paper_id": "fake_paper_1", "page": 3, "chunk_idx": 0},
                {"paper_id": "fake_paper_2", "page": 1, "chunk_idx": 0},
            ]],
            "distances": [[0.15, 0.42]],   # similarity: 0.85 / 0.58
        }

    col.query = fake_query
    col.count = MagicMock(return_value=2)
    return col
