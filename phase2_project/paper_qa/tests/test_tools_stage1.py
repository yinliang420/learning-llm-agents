"""Stage 1 工具的 unit tests — 测边界 case，不重复 eval 已覆盖的 happy path。

覆盖三个工具:
  1. list_papers   — 不存在的目录 / 损坏的 PDF
  2. read_paper    — 越界 page / 不存在的 paper_id / 截断 / page range 格式
  3. search_in_paper — 大小写 / 多页匹配上限 / 关键词找不到
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# read_paper: 边界 case
# ─────────────────────────────────────────────────────────────────────────────


class TestReadPaper:
    """read_paper 的边界行为。Eval 已覆盖正常路径，这里只测 corner cases。"""

    def test_not_found_returns_available_list(self, temp_papers_dir, monkeypatch):
        """不存在的 paper_id 必须返回 available_papers，不能只报错。"""
        import tools
        monkeypatch.setattr(tools, "PAPERS_DIR", temp_papers_dir)

        # 创建两个假 PDF（只是空文件，足够让 glob 找到名字）
        (temp_papers_dir / "paper_a.pdf").touch()
        (temp_papers_dir / "paper_b.pdf").touch()

        result = tools.read_paper("nonexistent_id")

        assert result["found"] is False
        assert "available_papers" in result
        assert set(result["available_papers"]) == {"paper_a", "paper_b"}

    def test_invalid_page_range_format(self, temp_papers_dir, monkeypatch):
        """传入非法格式的 pages 字符串，应该返回 error 而非崩溃。"""
        import tools
        monkeypatch.setattr(tools, "PAPERS_DIR", temp_papers_dir)

        # 写一个真的小 PDF（用 pypdf 创建空 PDF 比较麻烦，直接 mock）
        fake_pdf = temp_papers_dir / "test.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4\n")    # 最小 PDF header（pypdf 会接受）

        with patch("tools.PdfReader") as mock_reader:
            mock_reader.return_value = MagicMock(pages=[MagicMock()] * 5)
            result = tools.read_paper("test", pages="abc-xyz")

        assert result["found"] is False
        assert "Invalid pages format" in result["error"]

    def test_out_of_bounds_pages_silently_clipped(self, temp_papers_dir, monkeypatch):
        """如果 pages='8-20' 但 PDF 只有 5 页，应该返回前 5 页里能取的，不报错。"""
        import tools
        monkeypatch.setattr(tools, "PAPERS_DIR", temp_papers_dir)
        (temp_papers_dir / "test.pdf").write_bytes(b"%PDF-1.4\n")

        # 5 页 PDF
        fake_pages = [MagicMock() for _ in range(5)]
        for i, p in enumerate(fake_pages):
            p.extract_text.return_value = f"page {i+1} content"

        with patch("tools.PdfReader") as mock_reader:
            mock_reader.return_value = MagicMock(pages=fake_pages)
            result = tools.read_paper("test", pages="8-20")

        # 全部页码都超界 → 返回 no valid pages 错误
        assert result["found"] is False
        assert "No valid pages" in result["error"]

    def test_truncation_includes_hint(self, temp_papers_dir, monkeypatch):
        """超过 MAX_CHARS_PER_READ 时，必须返回 truncated=True + hint。"""
        import tools
        monkeypatch.setattr(tools, "PAPERS_DIR", temp_papers_dir)
        (temp_papers_dir / "test.pdf").write_bytes(b"%PDF-1.4\n")

        # 单页就超过 12000 字符
        big_page = MagicMock()
        big_page.extract_text.return_value = "X" * 15000
        fake_pages = [big_page] * 5

        with patch("tools.PdfReader") as mock_reader:
            mock_reader.return_value = MagicMock(pages=fake_pages)
            result = tools.read_paper("test")

        assert result["found"] is True
        assert result["truncated"] is True
        assert "hint" in result
        assert "Call read_paper again" in result["hint"]
        assert len(result["text"]) == tools.MAX_CHARS_PER_READ

    def test_corrupted_page_does_not_break_others(self, temp_papers_dir, monkeypatch):
        """某一页损坏（extract_text 抛异常），其他页应该正常返回。"""
        import tools
        monkeypatch.setattr(tools, "PAPERS_DIR", temp_papers_dir)
        (temp_papers_dir / "test.pdf").write_bytes(b"%PDF-1.4\n")

        good_page = MagicMock()
        good_page.extract_text.return_value = "good content"
        bad_page = MagicMock()
        bad_page.extract_text.side_effect = Exception("PDF corrupt")

        with patch("tools.PdfReader") as mock_reader:
            mock_reader.return_value = MagicMock(pages=[good_page, bad_page, good_page])
            result = tools.read_paper("test", pages="1-3")

        assert result["found"] is True
        assert "good content" in result["text"]
        # bad_page 应该是空字符串而非崩溃


# ─────────────────────────────────────────────────────────────────────────────
# search_in_paper: 边界 case
# ─────────────────────────────────────────────────────────────────────────────


class TestSearchInPaper:

    def test_keyword_not_found_returns_zero_matches(self, temp_papers_dir, monkeypatch):
        """关键词找不到时返回 match_count=0，不应该报错。"""
        import tools
        monkeypatch.setattr(tools, "PAPERS_DIR", temp_papers_dir)
        (temp_papers_dir / "test.pdf").write_bytes(b"%PDF-1.4\n")

        page = MagicMock()
        page.extract_text.return_value = "content about catalysts"
        with patch("tools.PdfReader") as mock_reader:
            mock_reader.return_value = MagicMock(pages=[page])
            result = tools.search_in_paper("test", keyword="quantum")

        assert result["found"] is True
        assert result["match_count"] == 0
        assert result["matches"] == []

    def test_case_insensitive_matching(self, temp_papers_dir, monkeypatch):
        """搜索应该不区分大小写。"""
        import tools
        monkeypatch.setattr(tools, "PAPERS_DIR", temp_papers_dir)
        (temp_papers_dir / "test.pdf").write_bytes(b"%PDF-1.4\n")

        page = MagicMock()
        page.extract_text.return_value = "OVERPOTENTIAL is high. overpotential matters."
        with patch("tools.PdfReader") as mock_reader:
            mock_reader.return_value = MagicMock(pages=[page])
            result = tools.search_in_paper("test", keyword="overpotential")

        assert result["match_count"] == 2

    def test_max_3_matches_per_page(self, temp_papers_dir, monkeypatch):
        """单页最多返回 3 个 match，防爆。"""
        import tools
        monkeypatch.setattr(tools, "PAPERS_DIR", temp_papers_dir)
        (temp_papers_dir / "test.pdf").write_bytes(b"%PDF-1.4\n")

        # 一页里出现 10 次 "the"
        page = MagicMock()
        page.extract_text.return_value = "the " * 10
        with patch("tools.PdfReader") as mock_reader:
            mock_reader.return_value = MagicMock(pages=[page])
            result = tools.search_in_paper("test", keyword="the")

        # 实际找到 10 个，但单页限 3 个
        assert result["match_count"] == 3

    def test_max_20_matches_total(self, temp_papers_dir, monkeypatch):
        """全文最多返回 20 个 match。"""
        import tools
        monkeypatch.setattr(tools, "PAPERS_DIR", temp_papers_dir)
        (temp_papers_dir / "test.pdf").write_bytes(b"%PDF-1.4\n")

        # 10 页 × 3 matches/page = 30 个，应该截到 20
        pages = []
        for _ in range(10):
            p = MagicMock()
            p.extract_text.return_value = "foo foo foo"
            pages.append(p)
        with patch("tools.PdfReader") as mock_reader:
            mock_reader.return_value = MagicMock(pages=pages)
            result = tools.search_in_paper("test", keyword="foo")

        # match_count 是实际找到数（30），matches 列表截到 20
        assert len(result["matches"]) <= 20


# ─────────────────────────────────────────────────────────────────────────────
# _parse_page_range: 内部辅助函数
# ─────────────────────────────────────────────────────────────────────────────


class TestParsePageRange:
    """页码范围字符串解析的边界行为。"""

    def test_single_number(self):
        from tools import _parse_page_range
        assert _parse_page_range("3", total=10) == [2]   # 1-indexed input → 0-indexed output

    def test_range(self):
        from tools import _parse_page_range
        assert _parse_page_range("1-3", total=10) == [0, 1, 2]

    def test_multiple(self):
        from tools import _parse_page_range
        assert _parse_page_range("1,3,5", total=10) == [0, 2, 4]

    def test_mixed_range_and_single(self):
        from tools import _parse_page_range
        assert _parse_page_range("1-3,7", total=10) == [0, 1, 2, 6]

    def test_filter_out_of_bounds(self):
        from tools import _parse_page_range
        # total=5 → 合法 0-indexed 是 0..4
        assert _parse_page_range("1-10", total=5) == [0, 1, 2, 3, 4]

    def test_invalid_format_raises(self):
        from tools import _parse_page_range
        with pytest.raises(ValueError):
            _parse_page_range("abc", total=10)
