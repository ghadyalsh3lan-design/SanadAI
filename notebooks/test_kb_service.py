"""
Integration test for the knowledge-base service (src/ingestion/kb_service.py).

Uses temporary directories so it never touches the real index or manifest.

Usage:
    python notebooks/test_kb_service.py
"""
import shutil
import tempfile
from pathlib import Path

import src.ingestion.kb_service as kb
from src.retrieval.vector_store import get_or_create_vector_store, count_chunks


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="kbtest_"))
    store_dir = tempfile.mkdtemp(prefix="kbstore_")
    # Isolate the manifest + KB folder from the real project data.
    kb.COMPANY_KB_DIR = tmp
    kb.MANIFEST_PATH = tmp / "_kb_manifest.json"

    sample = tmp / "sample_capability.md"
    sample.write_text(
        "# Capability\nIBTech delivers machine learning, RAG, and MLOps services "
        "for government clients.\n",
        encoding="utf-8",
    )

    try:
        vs = get_or_create_vector_store(persist_dir=store_dir, collection_name="kbtest")
        assert count_chunks(vs) == 0, "store should start empty"

        entry = kb.ingest_file(vs, sample, "capability")
        assert entry.doc_type == "capability"
        assert entry.chunk_count >= 1
        assert count_chunks(vs) == entry.chunk_count
        print(f"ingest: {entry.filename} -> {entry.chunk_count} chunks")

        docs = kb.list_documents()
        assert len(docs) == 1 and docs[0].doc_id == entry.doc_id
        print(f"list: {len(docs)} document(s)")

        strength = kb.kb_strength()
        cap = next(c for c in strength if c.doc_type == "capability")
        assert cap.count == 1
        thin = sum(1 for c in strength if c.is_thin)
        print(f"strength: capability={cap.count}, thin categories={thin}")

        removed = kb.delete_document(vs, entry.doc_id)
        assert removed == entry.chunk_count
        assert count_chunks(vs) == 0
        assert kb.list_documents() == []
        print(f"delete: removed {removed} chunks, store now empty")

        print("\nTest completed successfully.")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.rmtree(store_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
