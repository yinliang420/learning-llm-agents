"""Paper QA agent 的工具集（Stage 1：最小可用版）。

设计原则：
- 工具返回 structured JSON（学过的）
- 长文本默认截断 + 提示模型继续 read（学过的）
- 错误返回包含可用列表（学过的）
"""
from __future__ import annotations

from pathlib import Path
from pypdf import PdfReader

# Stage 1 用的小数据集
PAPERS_DIR = Path(__file__).parent / "papers_stage1"

# 单次 read_paper 最多返回多少字符（防 messages 爆炸）
MAX_CHARS_PER_READ = 12000
DEFAULT_FIRST_N_PAGES = 4  # 默认读前 4 页（一般包含 title / abstract / intro）


def _safe_text(page) -> str:
    """提取一页文本，失败返回空字符串。"""
    try:
        return page.extract_text() or ""
    except Exception:
        return ""


def list_papers() -> dict:
    """列出所有可用的论文，含基本元数据 + 第一页预览。

    Returns:
        {"papers": [{"id":..., "n_pages":..., "first_page_preview":...}, ...]}
    """
    papers = []
    for pdf in sorted(PAPERS_DIR.glob("*.pdf")):
        try:
            reader = PdfReader(pdf)
            preview = _safe_text(reader.pages[0])
            # 取前 300 字符做预览（够看到 title / abstract 开头）
            preview = " ".join(preview.split())[:300]
            papers.append({
                "id": pdf.stem,
                "n_pages": len(reader.pages),
                "first_page_preview": preview,
            })
        except Exception as e:
            papers.append({
                "id": pdf.stem,
                "error": f"{type(e).__name__}: {e}",
            })
    return {"papers": papers, "count": len(papers)}


def _parse_page_range(pages: str, total: int) -> list[int]:
    """解析 page 字符串成 0-indexed 列表。

    支持: "1", "1-3", "1,3,5", "1-3,7"
    """
    indices: set[int] = set()
    for part in pages.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-", 1)
            start_i, end_i = int(start) - 1, int(end) - 1
            indices.update(range(start_i, end_i + 1))
        else:
            indices.add(int(part) - 1)
    # 过滤越界
    return sorted(i for i in indices if 0 <= i < total)


def read_paper(paper_id: str, pages: str | None = None) -> dict:
    """读取论文的指定页或前 4 页文本。

    Args:
        paper_id: 论文文件名（不含 .pdf 扩展名）
        pages:    页码范围，如 "1-3" / "5" / "1,3,5" / "1-3,7"
                  None = 读前 4 页

    Returns:
        {"found": True, "text": ..., "pages_returned": [...], "truncated": bool, ...}
    """
    pdf_path = PAPERS_DIR / f"{paper_id}.pdf"

    if not pdf_path.exists():
        return {
            "found": False,
            "error": f"Paper '{paper_id}' not found",
            "available_papers": sorted(p.stem for p in PAPERS_DIR.glob("*.pdf")),
        }

    try:
        reader = PdfReader(pdf_path)
    except Exception as e:
        return {"found": False, "error": f"Failed to open PDF: {e}"}

    total = len(reader.pages)

    if pages is None:
        page_indices = list(range(min(DEFAULT_FIRST_N_PAGES, total)))
    else:
        try:
            page_indices = _parse_page_range(pages, total)
        except ValueError as e:
            return {
                "found": False,
                "error": f"Invalid pages format '{pages}': {e}. Use '1' or '1-3' or '1,3,5'.",
            }

    if not page_indices:
        return {
            "found": False,
            "error": f"No valid pages in range '{pages}' (total {total} pages)",
        }

    # 提取并组装文本
    parts = []
    for i in page_indices:
        text = _safe_text(reader.pages[i])
        text = " ".join(text.split())  # 压缩空白
        parts.append(f"[Page {i+1}]\n{text}")
    full_text = "\n\n".join(parts)

    truncated = False
    if len(full_text) > MAX_CHARS_PER_READ:
        full_text = full_text[:MAX_CHARS_PER_READ]
        truncated = True

    result = {
        "found": True,
        "paper_id": paper_id,
        "total_pages": total,
        "pages_returned": [i + 1 for i in page_indices],
        "text": full_text,
        "char_count": len(full_text),
        "truncated": truncated,
    }
    if truncated:
        last_page = page_indices[-1] + 1
        result["hint"] = (
            f"Text was truncated at {MAX_CHARS_PER_READ} chars. "
            f"Call read_paper again with pages='{last_page + 1}-{min(last_page + 4, total)}' to continue."
        )
    return result


def search_in_paper(paper_id: str, keyword: str, context_chars: int = 200) -> dict:
    """在论文里搜关键词，返回所有匹配位置 + 前后上下文。

    Args:
        paper_id: 论文文件名（不含 .pdf）
        keyword:  要搜索的关键词（不区分大小写）
        context_chars: 每个匹配位置的前后上下文字符数

    Returns:
        {"found": True, "matches": [{"page":..., "context":...}, ...]}
    """
    pdf_path = PAPERS_DIR / f"{paper_id}.pdf"
    if not pdf_path.exists():
        return {
            "found": False,
            "error": f"Paper '{paper_id}' not found",
            "available_papers": sorted(p.stem for p in PAPERS_DIR.glob("*.pdf")),
        }

    try:
        reader = PdfReader(pdf_path)
    except Exception as e:
        return {"found": False, "error": f"Failed to open PDF: {e}"}

    keyword_lower = keyword.lower()
    matches = []

    for i, page in enumerate(reader.pages):
        text = _safe_text(page)
        text_lower = text.lower()
        start = 0
        while True:
            pos = text_lower.find(keyword_lower, start)
            if pos == -1:
                break
            # 取前后上下文
            ctx_start = max(0, pos - context_chars)
            ctx_end = min(len(text), pos + len(keyword) + context_chars)
            context = " ".join(text[ctx_start:ctx_end].split())
            matches.append({
                "page": i + 1,
                "context": f"...{context}...",
            })
            start = pos + len(keyword)
            # 限制单页最多 3 个匹配，防止结果爆炸
            if len([m for m in matches if m["page"] == i + 1]) >= 3:
                break

    return {
        "found": True,
        "paper_id": paper_id,
        "keyword": keyword,
        "match_count": len(matches),
        "matches": matches[:20],  # 全文最多 20 个匹配
    }


# Dispatch 表给 agent 用
DISPATCH = {
    "list_papers": list_papers,
    "read_paper": read_paper,
    "search_in_paper": search_in_paper,
}
