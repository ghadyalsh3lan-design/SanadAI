"""
Chunker for the RFP Intelligence System.

Takes Documents from the parser and splits them into smaller chunks
suitable for embedding. Preserves all metadata so chunks know where
they came from (doc_id, source, source_type, page, etc.).

Uses RecursiveCharacterTextSplitter — splits on paragraph boundaries
first, then sentences, then words, only resorting to mid-word splits
as a last resort. This produces more semantically coherent chunks
than a naive fixed-size splitter.
"""
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src import config


# Defaults. All overridable via .env (see .env.example).
DEFAULT_CHUNK_SIZE = config.env_int("CHUNK_SIZE", 900)
DEFAULT_CHUNK_OVERLAP = config.env_int("CHUNK_OVERLAP", 150)

# A chunk shorter than this (after stripping) is too small to be useful evidence.
MIN_CHUNK_CHARS = config.env_int("MIN_CHUNK_CHARS", 80)
# A chunk with fewer than this fraction of alphanumeric characters is mostly
# separators (dots, pipes, dashes) — boilerplate, not content.
MIN_ALNUM_RATIO = config.env_float("MIN_ALNUM_RATIO", 0.5)


def _is_useful(text: str) -> bool:
    """True if a chunk carries enough real content to be worth indexing."""
    stripped = text.strip()
    if len(stripped) < MIN_CHUNK_CHARS:
        return False
    alnum = sum(c.isalnum() for c in stripped)
    return alnum / len(stripped) >= MIN_ALNUM_RATIO


def chunk_documents(
    documents: list[Document],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[Document]:
    """
    Split Documents into smaller chunks for embedding.

    Each chunk inherits all metadata from its parent Document, plus a
    chunk_index field marking its position within the source document.

    Args:
        documents: Output from src.ingestion.parser.parse_file
        chunk_size: Target characters per chunk. Default 500.
        chunk_overlap: Characters shared between adjacent chunks. Default 50.

    Returns:
        A list of Document objects, each one a chunk.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        # Split priority — paragraphs, then sentences, then words, then characters.
        separators=["\n\n", "\n", ". ", " ", ""],
        length_function=len,
    )

    chunks = splitter.split_documents(documents)

    # Drop low-value chunks (too short, or mostly separators) before indexing so
    # boilerplate doesn't crowd out real evidence at retrieval time.
    chunks = [c for c in chunks if _is_useful(c.page_content)]

    # Attach a chunk_index so we can trace where each chunk came from
    # within its source document. Useful for citation rendering later.
    for i, chunk in enumerate(chunks):
        chunk.metadata["chunk_index"] = i

    return chunks