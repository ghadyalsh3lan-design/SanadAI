"""
Knowledge-base service — the app-facing layer for building and managing the
company knowledge base without a terminal.

Wraps the existing parse -> chunk -> index pipeline with:
  - document typing (proposal, capability, cv, certification, ...),
  - incremental add (one upload at a time, into the live vector store),
  - a manifest so the UI can list and delete documents,
  - delete by document.

It deliberately does NOT own the vector store: callers pass in the live Chroma
instance (the same one the app searches), so add/delete mutate the store
in-process with no file-lock conflict. Parser, chunker, and vector_store are
unchanged — this module only orchestrates them and tracks a manifest.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from langchain_chroma import Chroma
from pydantic import BaseModel

from src.ingestion.parser import parse_file, SourceType
from src.ingestion.chunker import chunk_documents
from src.retrieval.vector_store import add_chunks, delete_document_chunks


COMPANY_KB_DIR = Path("data/company_kb")
MANIFEST_PATH = COMPANY_KB_DIR / "_kb_manifest.json"

DocType = Literal[
    "proposal", "capability", "case_study", "cv",
    "certification", "partner", "overview", "policy", "uncategorized",
]

# UI bucket labels, in display order. The label the PM picks IS the doc_type,
# so we never have to guess a document's category.
DOC_TYPE_LABELS: dict[str, str] = {
    "proposal": "Past proposals & RFP responses",
    "capability": "Capability statements",
    "case_study": "Case studies / project sheets",
    "cv": "CVs / resumes",
    "certification": "Certifications (ISO, partner)",
    "partner": "Partners / vendors / teaming",
    "overview": "Company overview & boilerplate",
    "policy": "Policies (security, QA, HSE)",
}

# Categories the strength meter expects to see covered.
EXPECTED_DOC_TYPES: list[str] = list(DOC_TYPE_LABELS.keys())


class KBDocument(BaseModel):
    """A single document tracked in the knowledge base."""
    doc_id: str
    filename: str
    doc_type: DocType
    added_at: str
    chunk_count: int


class CategoryStrength(BaseModel):
    """How many documents the KB holds for one category."""
    doc_type: str
    label: str
    count: int

    @property
    def is_thin(self) -> bool:
        return self.count == 0


# ---------------------------------------------------------------------------
# Manifest persistence
# ---------------------------------------------------------------------------

def _load_manifest() -> list[KBDocument]:
    """Internal: read the manifest, or return [] if it doesn't exist yet."""
    if not MANIFEST_PATH.exists():
        return []
    raw = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return [KBDocument(**entry) for entry in raw]


def _save_manifest(documents: list[KBDocument]) -> None:
    """Internal: write the manifest, creating the KB folder if needed."""
    COMPANY_KB_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(
        json.dumps([d.model_dump() for d in documents], indent=2),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def list_documents() -> list[KBDocument]:
    """Return all documents currently tracked in the knowledge base."""
    return _load_manifest()


def save_upload(file_bytes: bytes, filename: str) -> Path:
    """
    Persist an uploaded file into the company KB folder.

    Args:
        file_bytes: Raw file contents from the uploader.
        filename: Original filename (used as-is; a re-upload overwrites).

    Returns:
        The path the file was written to.
    """
    COMPANY_KB_DIR.mkdir(parents=True, exist_ok=True)
    dest = COMPANY_KB_DIR / filename
    dest.write_bytes(file_bytes)
    return dest


def ingest_file(
    vectorstore: Chroma,
    file_path: str | Path,
    doc_type: DocType,
    source_type: SourceType = "company_kb",
) -> KBDocument:
    """
    Parse, tag, chunk, and index one file into the live store; record it.

    Args:
        vectorstore: The live Chroma instance to add to.
        file_path: Path to a file already saved on disk (see save_upload).
        doc_type: The document's category, chosen by the user.
        source_type: Knowledge source; company_kb for the library.

    Returns:
        The KBDocument manifest entry that was recorded.

    Raises:
        ValueError: If no text could be extracted from the file.
        FileNotFoundError: If the file doesn't exist.
    """
    path = Path(file_path)
    documents = parse_file(path, source_type=source_type)
    for doc in documents:
        doc.metadata["doc_type"] = doc_type

    chunks = chunk_documents(documents)
    if not chunks:
        raise ValueError(f"No text could be extracted from {path.name}.")

    add_chunks(vectorstore, chunks)
    doc_id = chunks[0].metadata["doc_id"]  # all chunks from one file share it

    entry = KBDocument(
        doc_id=doc_id,
        filename=path.name,
        doc_type=doc_type,
        added_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        chunk_count=len(chunks),
    )
    # Replace any prior entry for the same doc_id, then append.
    manifest = [d for d in _load_manifest() if d.doc_id != doc_id]
    manifest.append(entry)
    _save_manifest(manifest)
    return entry


def delete_document(vectorstore: Chroma, doc_id: str) -> int:
    """
    Remove a document's chunks from the store and its manifest entry.

    Args:
        vectorstore: The live Chroma instance.
        doc_id: The document to remove.

    Returns:
        The number of chunks removed from the store.
    """
    removed = delete_document_chunks(vectorstore, doc_id)
    manifest = [d for d in _load_manifest() if d.doc_id != doc_id]
    _save_manifest(manifest)
    return removed


def sync_manifest_from_store(vectorstore: Chroma) -> list[KBDocument]:
    """
    Rebuild the manifest from whatever is already in the vector store.

    Used to bootstrap when an index was built by the CLI (scripts/index_corpus.py)
    and has no manifest yet, so existing documents still appear in the UI.
    Documents indexed before doc_type existed are tagged 'uncategorized'.

    Returns:
        The rebuilt list of KBDocument entries.
    """
    got = vectorstore._collection.get()
    metadatas = got.get("metadatas", []) or []

    by_doc: dict[str, dict] = {}
    for md in metadatas:
        doc_id = md.get("doc_id")
        if not doc_id:
            continue
        if doc_id not in by_doc:
            by_doc[doc_id] = {
                "doc_id": doc_id,
                "filename": md.get("source", "unknown"),
                "doc_type": md.get("doc_type", "uncategorized"),
                "added_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "chunk_count": 0,
            }
        by_doc[doc_id]["chunk_count"] += 1

    documents = [KBDocument(**entry) for entry in by_doc.values()]
    _save_manifest(documents)
    return documents


def kb_strength(documents: list[KBDocument] | None = None) -> list[CategoryStrength]:
    """
    Return per-category document counts for the KB-strength meter.

    Args:
        documents: Manifest to score; loads the current manifest if omitted.

    Returns:
        One CategoryStrength per expected category, in display order.
    """
    docs = documents if documents is not None else _load_manifest()
    counts: dict[str, int] = {}
    for d in docs:
        counts[d.doc_type] = counts.get(d.doc_type, 0) + 1
    return [
        CategoryStrength(doc_type=dt, label=DOC_TYPE_LABELS[dt], count=counts.get(dt, 0))
        for dt in EXPECTED_DOC_TYPES
    ]
