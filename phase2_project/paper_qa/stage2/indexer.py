"""Stage 2 RAG 索引器。

工作流：
  1. 扫描指定目录下的 PDF
  2. 对每篇 PDF 按页 + 重叠切 chunk
  3. 用 sentence-transformers 转 embedding（本地模型）
  4. 存入 chromadb（本地持久化文件）

之后 retriever.py 直接从这个 DB 检索。

用法：
    python indexer.py                  # 索引 stage1 的 5 篇
    python indexer.py --dir papers     # 索引完整藏书
    python indexer.py --reset          # 清空 DB 重建
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import chromadb
from chromadb.config import Settings
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer

# ─────────────────────────────────────────────────────────────────────────────
# 配置
# ─────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).parent
DB_PATH = SCRIPT_DIR / "chroma_db"      # 本地持久化目录
COLLECTION_NAME = "papers"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"   # 22MB，CPU 上够快

CHUNK_CHAR_SIZE = 800   # 单 chunk 约 800 字符（≈200 token，留余量）
CHUNK_OVERLAP = 200     # 相邻 chunk 重叠 200 字符（避免边界丢信息）

DEFAULT_PAPERS_DIR = SCRIPT_DIR.parent / "papers_stage1"


# ─────────────────────────────────────────────────────────────────────────────
# 切 chunk：按页 + 段内重叠
# ─────────────────────────────────────────────────────────────────────────────

def chunk_page_text(text: str, chunk_size: int = CHUNK_CHAR_SIZE,
                    overlap: int = CHUNK_OVERLAP) -> list[str]:
    """把一页文本切成多个有重叠的 chunk。"""
    text = " ".join(text.split())   # 压缩空白
    if len(text) <= chunk_size:
        return [text] if text else []

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start = end - overlap
    return chunks


def extract_chunks_from_pdf(pdf_path: Path) -> list[dict]:
    """单 PDF → list of chunk dicts。

    每个 chunk: {paper_id, page, chunk_idx, text}
    """
    reader = PdfReader(pdf_path)
    paper_id = pdf_path.stem
    result = []
    for page_num, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:
            continue
        for i, chunk in enumerate(chunk_page_text(text)):
            if len(chunk.strip()) < 50:   # 过滤太短的 chunk
                continue
            result.append({
                "paper_id": paper_id,
                "page": page_num,
                "chunk_idx": i,
                "text": chunk,
            })
    return result


# ─────────────────────────────────────────────────────────────────────────────
# 主索引流程
# ─────────────────────────────────────────────────────────────────────────────

def get_collection(reset: bool = False):
    """打开/创建 chromadb collection。"""
    client = chromadb.PersistentClient(
        path=str(DB_PATH),
        settings=Settings(anonymized_telemetry=False),
    )
    if reset:
        try:
            client.delete_collection(COLLECTION_NAME)
            print(f"  ℹ️  Reset: collection '{COLLECTION_NAME}' deleted")
        except Exception:
            pass
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},   # 余弦相似度
    )


def index_papers(papers_dir: Path, reset: bool = False) -> dict:
    """索引一个目录下的所有 PDF。"""
    pdfs = sorted(papers_dir.glob("*.pdf"))
    print(f"\n📁 Source: {papers_dir}")
    print(f"📄 Found {len(pdfs)} PDFs to index")

    print(f"🧠 Loading embedding model: {EMBEDDING_MODEL}")
    encoder = SentenceTransformer(EMBEDDING_MODEL)

    print(f"💾 Opening Chroma DB: {DB_PATH}")
    collection = get_collection(reset=reset)
    before_count = collection.count()
    print(f"   existing chunks in DB: {before_count}")

    total_chunks = 0
    skipped_papers = 0

    for i, pdf in enumerate(pdfs, 1):
        try:
            chunks = extract_chunks_from_pdf(pdf)
        except Exception as e:
            print(f"  ❌ [{i}/{len(pdfs)}] {pdf.name}: {type(e).__name__}: {e}")
            skipped_papers += 1
            continue

        if not chunks:
            print(f"  ⚠️  [{i}/{len(pdfs)}] {pdf.name}: no chunks (empty?)")
            continue

        # batch encode
        texts = [c["text"] for c in chunks]
        embeddings = encoder.encode(texts, show_progress_bar=False, convert_to_numpy=True)

        # 写入 chromadb
        ids = [f"{c['paper_id']}__p{c['page']}_c{c['chunk_idx']}" for c in chunks]
        metadatas = [{
            "paper_id": c["paper_id"],
            "page": c["page"],
            "chunk_idx": c["chunk_idx"],
        } for c in chunks]

        # upsert：可重复运行不会出错
        collection.upsert(
            ids=ids,
            embeddings=embeddings.tolist(),
            documents=texts,
            metadatas=metadatas,
        )

        total_chunks += len(chunks)
        print(f"  ✓ [{i}/{len(pdfs)}] {pdf.name}: {len(chunks)} chunks "
              f"(pages: {chunks[0]['page']}-{chunks[-1]['page']})")

    after_count = collection.count()
    print(f"\n✅ Done.")
    print(f"   Papers indexed: {len(pdfs) - skipped_papers} / {len(pdfs)}")
    print(f"   Chunks added/updated: {total_chunks}")
    print(f"   DB total chunks: {before_count} → {after_count}")

    return {
        "papers": len(pdfs) - skipped_papers,
        "chunks": after_count,
    }


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", type=Path, default=DEFAULT_PAPERS_DIR,
                        help="Papers directory to index")
    parser.add_argument("--reset", action="store_true",
                        help="Reset DB before indexing")
    args = parser.parse_args()

    index_papers(args.dir, reset=args.reset)
