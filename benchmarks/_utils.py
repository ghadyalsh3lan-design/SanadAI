"""
Shared helpers for the benchmark scripts.

These mirror the conventions in notebooks/ — standalone, run from the repo root,
importing src.* — but focus on measuring each RAG step and writing CSV results to
benchmarks/results/.
"""
import csv
import json
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from src.ingestion.parser import parse_file
from src.ingestion.chunker import chunk_documents
from src.retrieval.vector_store import index_chunks, search_with_scores, rerank

_BENCH_DIR = Path(__file__).resolve().parent
# Self-contained fixture: a small sample KB + golden QA grounded in it, so the
# benchmarks are reproducible and independent of the user's real data/company_kb.
SAMPLE_KB_DIR = _BENCH_DIR / "sample_kb"
GOLDEN_QA_PATH = _BENCH_DIR / "golden_qa.json"
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".md", ".txt"}
RESULTS_DIR = Path("benchmarks/results")


def kb_files() -> list[Path]:
    """Every indexable document in the benchmark sample knowledge base."""
    if not SAMPLE_KB_DIR.exists():
        return []
    return sorted(
        f for f in SAMPLE_KB_DIR.iterdir()
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
    )


def load_golden() -> list[dict]:
    """Load the benchmark golden QA set, skipping entries with empty ground truths."""
    if not GOLDEN_QA_PATH.exists():
        return []
    pairs = json.loads(GOLDEN_QA_PATH.read_text(encoding="utf-8"))
    return [p for p in pairs if p.get("ground_truth", "").strip()]


def write_csv(rows: list[dict], name: str) -> Path:
    """Write rows to benchmarks/results/<name>_<timestamp>.csv. Returns the path."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = RESULTS_DIR / f"{name}_{ts}.csv"
    if not rows:
        path.write_text("", encoding="utf-8")
        return path
    fieldnames = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def build_temp_index(chunk_size: int, overlap: int):
    """
    Build a throwaway Chroma index over the company KB with the given chunk
    settings. Returns (vectorstore, tmp_dir). Caller must rmtree tmp_dir.
    """
    all_chunks = []
    for f in kb_files():
        docs = parse_file(f, source_type="company_kb")
        all_chunks.extend(chunk_documents(docs, chunk_size=chunk_size, chunk_overlap=overlap))
    tmp_dir = tempfile.mkdtemp(prefix="rfp_bench_")
    vs = index_chunks(all_chunks, persist_dir=tmp_dir)
    return vs, tmp_dir


def cleanup(tmp_dir: str) -> None:
    """Remove a temp index directory, ignoring errors."""
    shutil.rmtree(tmp_dir, ignore_errors=True)


def precision_at_k(retrieved_sources: list[str], expected_sources, k: int) -> float:
    """Fraction of the top-k retrieved chunks whose source is an expected one."""
    expected = set(expected_sources or [])
    if not expected or k == 0:
        return 0.0
    topk = retrieved_sources[:k]
    if not topk:
        return 0.0
    hits = sum(1 for s in topk if s in expected)
    return hits / len(topk)


def retrieve_basic(vectorstore, query: str, k: int = 3):
    """Plain vector retrieval. Returns [(Document, score)]."""
    return search_with_scores(
        vectorstore, query, k=k, filter={"source_type": "company_kb"}
    )


def retrieve_reranked(vectorstore, query: str, k: int = 3):
    """Over-fetch by similarity, then cross-encoder rerank to k. [(Document, score)]."""
    candidates = search_with_scores(
        vectorstore, query, k=k * 4, filter={"source_type": "company_kb"}
    )
    docs = [doc for doc, _ in candidates]
    if not docs:
        return []
    return rerank(query, docs, k=k)


def sources_of(scored) -> list[str]:
    """Pull the source filenames (in order) from [(Document, score)] pairs."""
    return [doc.metadata.get("source", "") for doc, _ in scored]
