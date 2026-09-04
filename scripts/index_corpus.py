"""
Index the company knowledge base into the vector store.

Run once after dropping new documents into data/company_kb/.
Re-run to rebuild the index from scratch (clears previous index first).

Usage:
    python scripts/index_corpus.py
"""
import shutil
from pathlib import Path

from src.ingestion.parser import parse_file
from src.ingestion.chunker import chunk_documents
from src.retrieval.vector_store import index_chunks, DEFAULT_PERSIST_DIR


COMPANY_KB_DIR = Path("data/company_kb")
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".md", ".txt"}


def main() -> None:
    if not COMPANY_KB_DIR.exists():
        raise FileNotFoundError(f"Missing directory: {COMPANY_KB_DIR}")

    files = [
        f for f in COMPANY_KB_DIR.iterdir()
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
    ]

    if not files:
        raise RuntimeError(
            f"No documents found in {COMPANY_KB_DIR}. "
            f"Supported formats: {SUPPORTED_EXTENSIONS}"
        )

    # Clear previous index so re-runs don't create duplicate chunks
    persist_path = Path(DEFAULT_PERSIST_DIR)
    if persist_path.exists():
        shutil.rmtree(persist_path)
        print(f"Cleared existing index at {DEFAULT_PERSIST_DIR}")

    print(f"Found {len(files)} document(s) to index.\n")

    all_chunks = []
    for file_path in files:
        print(f"Processing: {file_path.name}")
        try:
            documents = parse_file(file_path, source_type="company_kb")
            chunks = chunk_documents(documents)
            all_chunks.extend(chunks)
            print(f"  -> {len(chunks)} chunks")
        except Exception as e:
            print(f"  -> FAILED: {e}")

    if not all_chunks:
        raise RuntimeError("Nothing was indexed. Check the failures above.")

    print(f"\nIndexing {len(all_chunks)} chunks into vector store...")
    index_chunks(all_chunks)
    print(f"Done. Index persisted to {DEFAULT_PERSIST_DIR}")


if __name__ == "__main__":
    main()
