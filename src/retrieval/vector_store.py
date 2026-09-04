"""
Vector store for the RFP Intelligence System.

Responsible for two things:
  1. Indexing: take chunks, embed them, persist to Chroma.
  2. Searching: take a query, return the top-k most similar chunks.

Uses sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 for
embeddings — multilingual (50+ languages including Arabic), 384 dimensions,
runs locally. Embeddings are L2-normalized and the Chroma collection uses
cosine distance, so the relevance scores returned by search_with_scores live
on a stable 0-1 scale and can be thresholded (see search_relevant /
DEFAULT_RELEVANCE_THRESHOLD).

IMPORTANT: changing the embedding model invalidates the existing Chroma
index. Delete ./chroma_db and re-run scripts/index_corpus.py after any
model change. Re-calibrate DEFAULT_RELEVANCE_THRESHOLD using
notebooks/debug_retrieval.py after re-indexing.

Chroma persists to ./chroma_db on disk so the index survives between
runs. Delete that folder to start fresh.
"""
import math
from pathlib import Path

from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

from src import config


# Defaults. All overridable via .env (see .env.example).
DEFAULT_EMBEDDING_MODEL = config.env_str(
    "EMBEDDING_MODEL",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
)
DEFAULT_PERSIST_DIR = config.env_str("CHROMA_PERSIST_DIR", "./chroma_db")
DEFAULT_COLLECTION_NAME = config.env_str("CHROMA_COLLECTION_NAME", "rfp_documents")

# Minimum relevance score (cosine similarity, ~0-1) a chunk must clear to be
# treated as real evidence. Below this, retrieval is considered too weak to
# ground an answer and callers should refuse rather than feed marginal context
# to the LLM. This is what makes "refusal over hallucination" a real mechanism
# instead of relying on the LLM's judgement.
#
# Originally calibrated for all-MiniLM-L6-v2. After switching to
# paraphrase-multilingual-MiniLM-L12-v2 + re-indexing, re-run
# notebooks/debug_retrieval.py to confirm 0.4 still cleanly separates
# in-domain from out-of-domain scores for this corpus.
DEFAULT_RELEVANCE_THRESHOLD = config.env_float("RELEVANCE_THRESHOLD", 0.4)

# Cosine distance keeps relevance scores comparable across queries.
_COLLECTION_METADATA = {"hnsw:space": "cosine"}

# Cross-encoder reranker. Bi-encoder (embedding) similarity ranks chunks by topic
# overlap, which can rank a keyword-dense boilerplate chunk above the one that
# actually answers the query. A cross-encoder scores (query, chunk) jointly and
# reorders by answer relevance. Loaded lazily and cached.
DEFAULT_RERANK_MODEL = config.env_str("RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
_reranker = None


def _get_reranker(model_name: str = DEFAULT_RERANK_MODEL):
    """Internal: build (once) and cache the cross-encoder reranker."""
    global _reranker
    if _reranker is None:
        from sentence_transformers import CrossEncoder

        _reranker = CrossEncoder(model_name)
    return _reranker


def rerank(
    query: str,
    documents: list[Document],
    k: int = 3,
    max_per_page: int | None = None,
) -> list[tuple[Document, float]]:
    """
    Re-rank candidate chunks by cross-encoder relevance to the query.

    Args:
        query: Natural language question.
        documents: Candidate chunks (e.g. from an over-fetched vector search).
        k: How many to return after reranking.
        max_per_page: Optional cap on chunks from any single (source, page).

    Returns:
        (Document, score) pairs, best first. Score is the cross-encoder logit
        squashed to 0-1 with a sigmoid, so it reads like the cosine relevance.
    """
    if not documents:
        return []

    reranker = _get_reranker()
    raw_scores = reranker.predict([(query, d.page_content) for d in documents])
    scored = sorted(
        ((doc, 1.0 / (1.0 + math.exp(-float(s)))) for doc, s in zip(documents, raw_scores)),
        key=lambda pair: pair[1],
        reverse=True,
    )

    if max_per_page is None:
        return scored[:k]

    picked: list[tuple[Document, float]] = []
    per_page: dict[tuple, int] = {}
    for doc, score in scored:
        key = (doc.metadata.get("source"), doc.metadata.get("page"))
        if per_page.get(key, 0) >= max_per_page:
            continue
        per_page[key] = per_page.get(key, 0) + 1
        picked.append((doc, score))
        if len(picked) >= k:
            break
    return picked


def _get_embeddings(model_name: str = DEFAULT_EMBEDDING_MODEL) -> HuggingFaceEmbeddings:
    """Internal: build the embedding model. Cached by HuggingFace after first load.

    normalize_embeddings=True pairs with the collection's cosine space so that
    relevance scores are well-behaved (a plain dot product on unit vectors).
    """
    return HuggingFaceEmbeddings(
        model_name=model_name,
        encode_kwargs={"normalize_embeddings": True},
    )


def index_chunks(
    chunks: list[Document],
    persist_dir: str = DEFAULT_PERSIST_DIR,
    collection_name: str = DEFAULT_COLLECTION_NAME,
    embedding_model: str = DEFAULT_EMBEDDING_MODEL,
) -> Chroma:
    """
    Embed chunks and store them in Chroma.

    Args:
        chunks: Output from src.ingestion.chunker.chunk_documents
        persist_dir: Where Chroma writes its files
        collection_name: Logical grouping inside Chroma
        embedding_model: HuggingFace model identifier

    Returns:
        The Chroma instance, ready to search.
    """
    embeddings = _get_embeddings(embedding_model)
    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=persist_dir,
        collection_name=collection_name,
        collection_metadata=_COLLECTION_METADATA,
    )
    return vectorstore


def load_vector_store(
    persist_dir: str = DEFAULT_PERSIST_DIR,
    collection_name: str = DEFAULT_COLLECTION_NAME,
    embedding_model: str = DEFAULT_EMBEDDING_MODEL,
) -> Chroma:
    """
    Open an existing Chroma index without re-embedding anything.

    Use this when the index has already been built and you just want to query.

    Returns:
        The Chroma instance, ready to search.

    Raises:
        FileNotFoundError: If the persist directory doesn't exist.
    """
    if not Path(persist_dir).exists():
        raise FileNotFoundError(
            f"No vector store at {persist_dir}. Run index_chunks first."
        )
    embeddings = _get_embeddings(embedding_model)
    return Chroma(
        persist_directory=persist_dir,
        collection_name=collection_name,
        embedding_function=embeddings,
        collection_metadata=_COLLECTION_METADATA,
    )


def search_with_scores(
    vectorstore: Chroma,
    query: str,
    k: int = 3,
    filter: dict | None = None,
    fetch_k: int | None = None,
    max_per_page: int | None = None,
) -> list[tuple[Document, float]]:
    """
    Find the top-k most relevant chunks for a query, with relevance scores.

    Args:
        vectorstore: A Chroma instance from index_chunks or load_vector_store.
        query: Natural language question.
        k: How many chunks to return.
        filter: Optional metadata filter, e.g. {"source_type": "company_kb"}.
        fetch_k: How many candidates to pull before applying the per-page cap.
            Defaults to k * 4 when max_per_page is set; ignored otherwise.
        max_per_page: Cap on chunks returned from any single (source, page) so
            one page can't dominate the results. None disables the cap.

    Returns:
        (Document, score) pairs ranked most-relevant first. Score is cosine
        similarity, roughly 0-1, where higher means more relevant.
    """
    if max_per_page is None:
        return vectorstore.similarity_search_with_relevance_scores(
            query, k=k, filter=filter
        )

    candidates = vectorstore.similarity_search_with_relevance_scores(
        query, k=fetch_k or k * 4, filter=filter
    )
    picked: list[tuple[Document, float]] = []
    per_page: dict[tuple, int] = {}
    for doc, score in candidates:
        key = (doc.metadata.get("source"), doc.metadata.get("page"))
        if per_page.get(key, 0) >= max_per_page:
            continue
        per_page[key] = per_page.get(key, 0) + 1
        picked.append((doc, score))
        if len(picked) >= k:
            break
    return picked


def search(
    vectorstore: Chroma,
    query: str,
    k: int = 3,
    filter: dict | None = None,
) -> list[Document]:
    """
    Find the top-k most relevant chunks for a query.

    Thin wrapper over search_with_scores that drops the scores, for callers
    that don't need a relevance gate.

    Returns:
        Documents ranked by similarity, most similar first.
    """
    return [doc for doc, _score in search_with_scores(vectorstore, query, k=k, filter=filter)]


def get_or_create_vector_store(
    persist_dir: str = DEFAULT_PERSIST_DIR,
    collection_name: str = DEFAULT_COLLECTION_NAME,
    embedding_model: str = DEFAULT_EMBEDDING_MODEL,
) -> Chroma:
    """
    Open the Chroma index, creating an empty one if it doesn't exist yet.

    Unlike load_vector_store, this never raises on a missing directory. It is
    what the app uses so a first-run user starts from an empty, writable store
    (and can build their knowledge base from the UI) instead of hitting an error.

    Returns:
        A Chroma instance, possibly empty, ready to add to or search.
    """
    embeddings = _get_embeddings(embedding_model)
    return Chroma(
        persist_directory=persist_dir,
        collection_name=collection_name,
        embedding_function=embeddings,
        collection_metadata=_COLLECTION_METADATA,
    )


def add_chunks(vectorstore: Chroma, chunks: list[Document]) -> list[str]:
    """
    Add already-chunked documents to an existing store (incremental indexing).

    Args:
        vectorstore: A live Chroma instance.
        chunks: Output from src.ingestion.chunker.chunk_documents.

    Returns:
        The ids assigned to the added chunks (empty if chunks was empty).
    """
    if not chunks:
        return []
    return vectorstore.add_documents(chunks)


def delete_document_chunks(vectorstore: Chroma, doc_id: str) -> int:
    """
    Remove every chunk belonging to a document.

    Args:
        vectorstore: A live Chroma instance.
        doc_id: The doc_id shared by all of a document's chunks.

    Returns:
        The number of chunks removed.
    """
    existing = vectorstore._collection.get(where={"doc_id": doc_id})
    ids = existing.get("ids", []) or []
    if ids:
        vectorstore._collection.delete(ids=ids)
    return len(ids)


def count_chunks(vectorstore: Chroma) -> int:
    """Return the total number of chunks currently in the store."""
    return vectorstore._collection.count()


def search_relevant(
    vectorstore: Chroma,
    query: str,
    k: int = 3,
    filter: dict | None = None,
    threshold: float = DEFAULT_RELEVANCE_THRESHOLD,
) -> list[Document]:
    """
    Like search(), but drops chunks whose relevance falls below `threshold`.

    Returning an empty list is a meaningful signal: retrieval found nothing
    convincing, so the caller should refuse rather than answer from weak
    context. This is the retrieval-side half of "refusal over hallucination".

    Args:
        vectorstore: A Chroma instance.
        query: Natural language question.
        k: How many chunks to consider before filtering.
        filter: Optional metadata filter.
        threshold: Minimum relevance score to keep a chunk.

    Returns:
        Relevant Documents, most similar first. May be empty.
    """
    return [
        doc
        for doc, score in search_with_scores(vectorstore, query, k=k, filter=filter)
        if score >= threshold
    ]
