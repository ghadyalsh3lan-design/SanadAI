"""
Incoming-RFP service — stores RFP documents the team is considering bidding on.

Unlike the company knowledge base, incoming RFPs are NOT indexed into the vector
store. They are just saved to disk so the Analyze page can list them and let the
user pick one to run a pre-bid analysis against, without re-uploading each time.

Files live in data/incoming_rfps/. The directory listing IS the source of truth,
so there is no separate manifest to keep in sync.
"""
from datetime import datetime, timezone
from pathlib import Path

from langchain_chroma import Chroma
from pydantic import BaseModel

from src.ingestion.parser import parse_file
from src.ingestion.chunker import chunk_documents
from src.retrieval.vector_store import add_chunks

INCOMING_RFP_DIR = Path("data/incoming_rfps")
ALLOWED_EXT = {".pdf", ".docx", ".pptx", ".md", ".txt"}
RFP_SOURCE_TYPE = "incoming_rfp"


class IncomingRFP(BaseModel):
    """A saved incoming RFP document available for analysis."""
    filename: str
    size_kb: int
    added_at: str


def _safe_path(filename: str) -> Path:
    """Resolve a filename inside the RFP dir, rejecting path traversal."""
    name = Path(filename).name  # strip any directory components
    if not name or name.startswith("."):
        raise ValueError(f"Invalid filename '{filename}'.")
    return INCOMING_RFP_DIR / name


def list_rfps() -> list[IncomingRFP]:
    """Return all saved incoming RFPs, newest first."""
    if not INCOMING_RFP_DIR.exists():
        return []
    rfps = []
    for p in INCOMING_RFP_DIR.iterdir():
        if not p.is_file() or p.suffix.lower() not in ALLOWED_EXT:
            continue
        stat = p.stat()
        rfps.append(
            IncomingRFP(
                filename=p.name,
                size_kb=max(1, round(stat.st_size / 1024)),
                added_at=datetime.fromtimestamp(
                    stat.st_mtime, tz=timezone.utc
                ).isoformat(timespec="seconds"),
            )
        )
    return sorted(rfps, key=lambda r: r.added_at, reverse=True)


def save_rfp(file_bytes: bytes, filename: str) -> IncomingRFP:
    """
    Persist an uploaded incoming RFP. A re-upload overwrites the same name.

    Raises:
        ValueError: If the filename is invalid or the type is unsupported.
    """
    dest = _safe_path(filename)
    if dest.suffix.lower() not in ALLOWED_EXT:
        raise ValueError(
            f"Unsupported file type '{dest.suffix}'. "
            f"Allowed: {', '.join(sorted(ALLOWED_EXT))}"
        )
    INCOMING_RFP_DIR.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(file_bytes)
    stat = dest.stat()
    return IncomingRFP(
        filename=dest.name,
        size_kb=max(1, round(stat.st_size / 1024)),
        added_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(
            timespec="seconds"
        ),
    )


def rfp_path(filename: str) -> Path:
    """Return the on-disk path for a saved RFP, or raise if it's missing."""
    path = _safe_path(filename)
    if not path.is_file():
        raise FileNotFoundError(f"No saved RFP named '{filename}'.")
    return path


def delete_rfp(filename: str) -> bool:
    """Delete a saved incoming RFP. Returns True if a file was removed."""
    path = _safe_path(filename)
    if not path.is_file():
        return False
    path.unlink()
    return True


# ---------------------------------------------------------------------------
# Vector-store indexing — makes incoming RFPs searchable on the Ask page
# ---------------------------------------------------------------------------

def _rfp_chunk_ids(vectorstore: Chroma, filename: str) -> list[str]:
    """Internal: ids of all indexed chunks belonging to one incoming RFP."""
    got = vectorstore._collection.get(
        where={"$and": [{"source": filename}, {"source_type": RFP_SOURCE_TYPE}]}
    )
    return got.get("ids", []) or []


def index_rfp(vectorstore: Chroma, filename: str) -> int:
    """
    Parse, chunk, and index an incoming RFP into the live vector store so it can
    be retrieved on the Ask page. Re-indexing the same filename replaces its
    prior chunks first. Returns the number of chunks indexed.
    """
    path = rfp_path(filename)
    stale = _rfp_chunk_ids(vectorstore, path.name)
    if stale:
        vectorstore._collection.delete(ids=stale)

    documents = parse_file(path, source_type=RFP_SOURCE_TYPE)
    chunks = chunk_documents(documents)
    if chunks:
        add_chunks(vectorstore, chunks)
    return len(chunks)


def unindex_rfp(vectorstore: Chroma, filename: str) -> int:
    """Remove an incoming RFP's chunks from the vector store. Returns count."""
    ids = _rfp_chunk_ids(vectorstore, Path(filename).name)
    if ids:
        vectorstore._collection.delete(ids=ids)
    return len(ids)


def reindex_all(vectorstore: Chroma) -> int:
    """Index every saved RFP not already represented in the store (backfill)."""
    total = 0
    for rfp in list_rfps():
        if not _rfp_chunk_ids(vectorstore, rfp.filename):
            total += index_rfp(vectorstore, rfp.filename)
    return total
