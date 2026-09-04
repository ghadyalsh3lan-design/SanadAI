"""
FastAPI server for the RFP Intelligence System.

Endpoints:
  GET    /health                    — liveness probe
  POST   /query                     — Q&A against the company knowledge base (filters + top-k)
  POST   /evaluate                   — LLM-as-a-judge scoring of an answer
  GET    /chat/sessions             — list saved chat sessions
  GET    /chat/sessions/{id}        — load a chat session
  POST   /chat/sessions             — create/update a chat session
  DELETE /chat/sessions/{id}        — delete a chat session
  POST   /analyze-rfp               — upload an RFP and get a pre-bid analysis report
  GET    /rfps                       — list saved incoming RFPs
  POST   /rfps                       — save an uploaded incoming RFP
  DELETE /rfps/{filename}            — delete a saved incoming RFP
  POST   /rfps/{filename}/analyze    — analyze a saved incoming RFP
  POST   /rfps/{filename}/draft      — draft a proposal from a saved incoming RFP
  POST   /rfps/{filename}/draft/section — regenerate one section from a saved RFP
  POST   /draft-proposal            — upload an RFP and get a multi-section draft
  POST   /draft-proposal/section    — regenerate a single proposal section
  GET    /kb/documents              — list knowledge base documents
  GET    /kb/stats                  — KB summary (counts + category coverage)
  POST   /kb/documents              — upload + index a document (multipart: file, doc_type)
  DELETE /kb/documents/{id}         — remove a document from the KB
  POST   /export/analysis           — download a pre-bid report as Word
  POST   /export/proposal           — download a proposal draft as Word
  GET    /workspace/bids            — list tracked RFP bids
  POST   /workspace/bids            — add a new bid
  PATCH  /workspace/bids/{id}       — update bid status
  DELETE /workspace/bids/{id}       — remove a bid

Run with:
    uvicorn src.api.main:app --reload
"""
import os
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src import config  # noqa: F401 — loads .env via side effect
from src.retrieval.vector_store import (
    get_or_create_vector_store,
    count_chunks,
    DEFAULT_RELEVANCE_THRESHOLD,
)
from src.generation.generator import generate_answer, condense_question, Answer, Source
from src.generation.verifier import verify_answer, VerificationResult
from src.generation.judge import evaluate_answer, EvaluationResponse
from src.retrieval.vector_store import search_with_scores, rerank
from src.chat import chat_service
from src.chat.chat_service import ChatSession, ChatSessionSummary
from src.analysis.pre_bid import analyze_rfp, PreBidAnalysis
from src.drafting.proposal import draft_proposal, draft_single_section, ProposalDraft, ProposalSection
from src.workspace import workspace_service
from src.workspace.workspace_service import WorkspaceBid
from src.drafting.export import prebid_report_to_docx_bytes, proposal_to_docx_bytes
from src.ingestion.parser import parse_file
from src.ingestion import kb_service, rfp_service
from src.ingestion.kb_service import KBDocument, CategoryStrength, DOC_TYPE_LABELS
from src.ingestion.rfp_service import IncomingRFP

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

# Cap on chunks a single page may contribute to a /query result, so one page
# can't dominate the citations. Overridable via .env (see .env.example).
QUERY_MAX_PER_PAGE = config.env_int("QUERY_MAX_PER_PAGE", 2)
# Minimum candidates to over-fetch before cross-encoder reranking.
RERANK_FETCH_K = config.env_int("RERANK_FETCH_K", 20)

# In-memory app state — populated at startup, used by every request
state: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Open (or create) the vector store at startup; clear state on shutdown.

    Uses get_or_create so the API also serves a brand-new, empty knowledge base
    (the frontend builds it up via the /kb endpoints). The persist directory is
    overridable with the CHROMA_DIR env var, which keeps tests isolated.
    """
    persist_dir = os.getenv("CHROMA_DIR", "./chroma_db")
    state["vectorstore"] = get_or_create_vector_store(persist_dir=persist_dir)
    # Bootstrap the document manifest from an existing (CLI-built) index if empty.
    if not kb_service.list_documents() and count_chunks(state["vectorstore"]) > 0:
        kb_service.sync_manifest_from_store(state["vectorstore"])
    # Index any incoming RFPs saved before they were made searchable.
    indexed = rfp_service.reindex_all(state["vectorstore"])
    if indexed:
        print(f"Backfilled {indexed} incoming-RFP chunks into the index.")
    print("Vector store ready. API up.")
    yield
    state.clear()


app = FastAPI(
    title="RFP Intelligence System",
    description=(
        "A RAG-based assistant for proposal writers. "
        "Answer questions from the company knowledge base, "
        "or upload an incoming RFP for a pre-bid coverage analysis."
    ),
    version="0.3.0",
    lifespan=lifespan,
)

# Allow the local React dev server (Vite) to call the API during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:3000", "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class QueryRequest(BaseModel):
    """Incoming query payload."""
    question: str = Field(
        description="The user's question",
        min_length=1,
        max_length=1000,
    )
    k: int = Field(
        default=3,
        description="Number of chunks to retrieve (top-k)",
        ge=1,
        le=20,
    )
    verify: bool = Field(
        default=False,
        description="Run a faithfulness + completeness check on the answer",
    )
    doc_types: list[str] | None = Field(
        default=None,
        description="Restrict retrieval to these document categories",
    )
    sources: list[str] | None = Field(
        default=None,
        description="Restrict retrieval to these specific document filenames",
    )
    include_rfps: bool = Field(
        default=False,
        description="Also search indexed incoming RFP documents, not just the company KB",
    )
    history: list[dict] | None = Field(
        default=None,
        description="Prior conversation turns ([{role, content}]) for chat memory",
    )


def _build_kb_filter(
    doc_types: list[str] | None = None,
    sources: list[str] | None = None,
    include_rfps: bool = False,
) -> dict:
    """
    Build a Chroma metadata filter for retrieval.

    Scopes to the company KB by default; when include_rfps is set, indexed
    incoming RFPs are searched too. Optionally narrows by document category
    (doc_type) and/or specific document (source filename). Chroma requires an
    explicit $and when combining more than one condition.
    """
    source_types = ["company_kb"]
    if include_rfps:
        source_types.append("incoming_rfp")
    base = (
        {"source_type": source_types[0]}
        if len(source_types) == 1
        else {"source_type": {"$in": source_types}}
    )
    conditions: list[dict] = [base]
    if doc_types:
        conditions.append({"doc_type": {"$in": doc_types}})
    if sources:
        conditions.append({"source": {"$in": sources}})
    if len(conditions) == 1:
        return conditions[0]
    return {"$and": conditions}


class QueryResponse(BaseModel):
    """Answer plus optional verification result."""
    answer: str
    sources: list[Source]
    refused: bool
    verification: VerificationResult | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
def health() -> dict:
    """Liveness probe — confirms the server is up and the vector store is loaded."""
    return {"status": "ok", "vectorstore_loaded": "vectorstore" in state}


def _retrieve_reranked(
    question: str,
    k: int,
    doc_types: list[str] | None,
    sources: list[str] | None,
    include_rfps: bool,
) -> list[tuple]:
    """
    Two-stage KB retrieval shared by /query and /evaluate.

    Over-fetches by embedding similarity (cheap, wide net), applies the relevance
    gate, then re-ranks the survivors with a cross-encoder so the chunk that
    actually answers the question ranks first. Using the same path for /evaluate
    means the LLM judge sees exactly the context the answer was grounded in.

    The gate is relaxed when the user explicitly scopes to specific documents or
    categories — they've already narrowed the search themselves.

    Returns (Document, score) pairs, best first; score is the cross-encoder
    relevance (0-1).
    """
    explicitly_scoped = bool(sources) or bool(doc_types)
    threshold = 0.0 if explicitly_scoped else DEFAULT_RELEVANCE_THRESHOLD
    fetch_k = max(k * 4, RERANK_FETCH_K)
    scored = search_with_scores(
        state["vectorstore"],
        question,
        k=fetch_k,
        filter=_build_kb_filter(doc_types, sources, include_rfps),
    )
    survivors = [(doc, score) for doc, score in scored if score >= threshold]
    try:
        return rerank(question, [doc for doc, _ in survivors], k=k, max_per_page=QUERY_MAX_PER_PAGE)
    except Exception:
        # Reranker unavailable — fall back to cosine order.
        return survivors[:k]


@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest) -> QueryResponse:
    """
    Answer a question grounded in the company knowledge base.

    Set verify=true to also receive a faithfulness and completeness check
    on the generated answer.
    """
    if "vectorstore" not in state:
        raise HTTPException(
            status_code=503,
            detail="Vector store not loaded. Restart the server.",
        )

    # With chat memory, a follow-up ("what about its deadline?") is rephrased into
    # a standalone question so retrieval finds the right chunks.
    search_question = condense_question(request.question, request.history)
    reranked = _retrieve_reranked(
        search_question, request.k, request.doc_types, request.sources, request.include_rfps
    )
    retrieved = []
    for doc, score in reranked:
        doc.metadata["relevance"] = round(score, 3)
        retrieved.append(doc)

    if not retrieved:
        return QueryResponse(
            answer="I don't have enough information to answer that based on the provided documents.",
            sources=[],
            refused=True,
        )

    answer: Answer = generate_answer(request.question, retrieved, history=request.history)

    verification = None
    if request.verify and not answer.refused:
        verification = verify_answer(request.question, answer.answer, retrieved)

    return QueryResponse(
        answer=answer.answer,
        sources=answer.sources,
        refused=answer.refused,
        verification=verification,
    )


# ---------------------------------------------------------------------------
# LLM-as-a-Judge — evaluate a generated answer
# ---------------------------------------------------------------------------

class EvaluateRequest(BaseModel):
    """Evaluate a previously generated answer. Context is re-retrieved server-side."""
    question: str = Field(min_length=1, max_length=1000)
    answer: str = Field(min_length=1)
    k: int = Field(default=3, ge=1, le=20)
    doc_types: list[str] | None = None
    sources: list[str] | None = None
    include_rfps: bool = False


@app.post("/evaluate", response_model=EvaluationResponse)
def evaluate(request: EvaluateRequest) -> EvaluationResponse:
    """
    Score an answer with an LLM judge (faithfulness, relevance, completeness,
    groundedness, citation quality, hallucination).

    The grounding context is re-retrieved with the same two-stage (embedding +
    cross-encoder) pipeline as /query, so the judge sees exactly the context the
    answer was grounded in — not a different, lower-ranked set of chunks.
    """
    if "vectorstore" not in state:
        raise HTTPException(status_code=503, detail="Vector store not loaded.")

    reranked = _retrieve_reranked(
        request.question, request.k, request.doc_types, request.sources, request.include_rfps
    )
    context = [doc.page_content for doc, _ in reranked]
    citations = [
        {
            "source": doc.metadata.get("source", "unknown"),
            "page": doc.metadata.get("page"),
            "score": round(score, 3),
        }
        for doc, score in reranked
    ]
    return evaluate_answer(request.question, request.answer, context, citations)


async def _extract_rfp_text(file: UploadFile) -> tuple[str, str]:
    """
    Validate an uploaded RFP, parse it, and return (rfp_text, filename).

    Shared by /analyze-rfp and /draft-proposal.

    Raises:
        HTTPException: 503 if the vector store isn't loaded, 400 for an
                       unsupported file type.
    """
    if "vectorstore" not in state:
        raise HTTPException(
            status_code=503,
            detail="Vector store not loaded. Restart the server.",
        )

    suffix = Path(file.filename or "upload").suffix.lower()
    allowed = {".pdf", ".docx", ".pptx", ".md", ".txt"}
    if suffix not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Allowed: {', '.join(sorted(allowed))}",
        )

    # Write upload to a temp file — parser.parse_file needs a file path
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        rfp_text = _parse_rfp_path(tmp_path)
        return rfp_text, (file.filename or "uploaded_rfp")
    finally:
        os.unlink(tmp_path)


def _parse_rfp_path(path: str | Path) -> str:
    """Parse an RFP file on disk into a single text blob."""
    documents = parse_file(path, source_type="incoming_rfp")
    return "\n\n".join(doc.page_content for doc in documents)


@app.post("/analyze-rfp", response_model=PreBidAnalysis)
async def analyze_rfp_endpoint(file: UploadFile = File(...)) -> PreBidAnalysis:
    """
    Upload an RFP document and receive a pre-bid analysis report.

    The report includes:
    - A requirement coverage table (fully/partially/not covered, with evidence)
    - Severity-tagged clarifying questions (blocker / important / nice_to_clarify)
    - A summary count at each coverage level

    Supported formats: PDF, DOCX, PPTX, MD, TXT
    """
    rfp_text, filename = await _extract_rfp_text(file)
    try:
        return analyze_rfp(rfp_text, filename, state["vectorstore"])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Incoming RFPs — saved documents the team can pick from to analyze
# ---------------------------------------------------------------------------

@app.get("/rfps", response_model=list[IncomingRFP])
def list_rfps() -> list[IncomingRFP]:
    """List incoming RFPs saved on disk, newest first."""
    return rfp_service.list_rfps()


@app.post("/rfps", response_model=IncomingRFP)
async def upload_rfp(file: UploadFile = File(...)) -> IncomingRFP:
    """Save an uploaded incoming RFP and index it so it's searchable on Ask."""
    content = await file.read()
    try:
        saved = rfp_service.save_rfp(content, file.filename or "uploaded_rfp")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if "vectorstore" in state:
        try:
            rfp_service.index_rfp(state["vectorstore"], saved.filename)
        except ValueError:
            pass  # unparseable RFP still saved; just not searchable
    return saved


@app.delete("/rfps/{filename}")
def delete_rfp(filename: str) -> dict:
    """Delete a saved incoming RFP and remove it from the index."""
    if "vectorstore" in state:
        rfp_service.unindex_rfp(state["vectorstore"], filename)
    if not rfp_service.delete_rfp(filename):
        raise HTTPException(status_code=404, detail=f"No saved RFP named '{filename}'.")
    return {"filename": filename, "deleted": True}


@app.post("/rfps/{filename}/analyze", response_model=PreBidAnalysis)
def analyze_saved_rfp(filename: str) -> PreBidAnalysis:
    """Run a pre-bid analysis against a previously saved incoming RFP."""
    if "vectorstore" not in state:
        raise HTTPException(status_code=503, detail="Vector store not loaded.")
    try:
        path = rfp_service.rfp_path(filename)
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(status_code=404, detail=str(e))
    rfp_text = _parse_rfp_path(path)
    try:
        return analyze_rfp(rfp_text, path.name, state["vectorstore"])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


def _saved_rfp_text(filename: str) -> tuple[str, str]:
    """Resolve a saved RFP and return (rfp_text, filename), raising HTTP errors."""
    if "vectorstore" not in state:
        raise HTTPException(status_code=503, detail="Vector store not loaded.")
    try:
        path = rfp_service.rfp_path(filename)
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(status_code=404, detail=str(e))
    return _parse_rfp_path(path), path.name


@app.post("/rfps/{filename}/draft", response_model=ProposalDraft)
def draft_saved_rfp(filename: str) -> ProposalDraft:
    """Generate a full proposal draft from a previously saved incoming RFP."""
    rfp_text, name = _saved_rfp_text(filename)
    try:
        return draft_proposal(rfp_text, name, state["vectorstore"])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/rfps/{filename}/draft/section", response_model=ProposalSection)
def draft_saved_rfp_section(filename: str, section_title: str = Form(...)) -> ProposalSection:
    """Regenerate a single proposal section from a saved incoming RFP."""
    rfp_text, _ = _saved_rfp_text(filename)
    try:
        return draft_single_section(rfp_text, section_title, state["vectorstore"])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/draft-proposal/section", response_model=ProposalSection)
async def draft_section_endpoint(
    file: UploadFile = File(...),
    section_title: str = Form(...),
) -> ProposalSection:
    """
    Regenerate a single section of a proposal draft.

    Useful for iterating on a specific section without re-running the full draft.
    section_title must match one of the default section titles exactly
    (case-insensitive).

    Supported formats: PDF, DOCX, PPTX, MD, TXT
    """
    rfp_text, _ = await _extract_rfp_text(file)
    try:
        return draft_single_section(rfp_text, section_title, state["vectorstore"])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/draft-proposal", response_model=ProposalDraft)
async def draft_proposal_endpoint(file: UploadFile = File(...)) -> ProposalDraft:
    """
    Upload an RFP document and receive a full multi-section proposal draft.

    Each section is generated with per-section retrieval from the company
    knowledge base and cites the sources it was grounded in. Sections without
    real KB evidence are flagged for review. This is the ambitious end of the
    pipeline — review every draft before submission.

    Supported formats: PDF, DOCX, PPTX, MD, TXT
    """
    rfp_text, filename = await _extract_rfp_text(file)
    try:
        return draft_proposal(rfp_text, filename, state["vectorstore"])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Knowledge base management (used by the frontend's setup + dashboard)
# ---------------------------------------------------------------------------

_ALLOWED_KB_EXT = {".pdf", ".docx", ".pptx", ".md", ".txt"}


class KBStats(BaseModel):
    """Dashboard summary of the knowledge base."""
    documents: int
    sections: int
    last_updated: str | None = None
    strength: list[CategoryStrength]


@app.get("/kb/documents", response_model=list[KBDocument])
def kb_list_documents() -> list[KBDocument]:
    """List the documents currently in the knowledge base."""
    return kb_service.list_documents()


@app.get("/kb/stats", response_model=KBStats)
def kb_get_stats() -> KBStats:
    """Counts, last-updated, and per-category coverage for the dashboard."""
    docs = kb_service.list_documents()
    last = max((d.added_at for d in docs), default=None)
    sections = count_chunks(state["vectorstore"]) if "vectorstore" in state else 0
    return KBStats(
        documents=len(docs),
        sections=sections,
        last_updated=last,
        strength=kb_service.kb_strength(docs),
    )


@app.post("/kb/documents", response_model=KBDocument)
async def kb_add_document(
    file: UploadFile = File(...),
    doc_type: str = Form(...),
) -> KBDocument:
    """Upload a file, tag it with a document type, and index it into the KB."""
    if "vectorstore" not in state:
        raise HTTPException(status_code=503, detail="Vector store not loaded.")
    if doc_type not in DOC_TYPE_LABELS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown doc_type '{doc_type}'. Allowed: {', '.join(DOC_TYPE_LABELS)}",
        )
    suffix = Path(file.filename or "upload").suffix.lower()
    if suffix not in _ALLOWED_KB_EXT:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Allowed: {', '.join(sorted(_ALLOWED_KB_EXT))}",
        )
    content = await file.read()
    path = kb_service.save_upload(content, file.filename or f"upload{suffix}")
    try:
        return kb_service.ingest_file(state["vectorstore"], path, doc_type)  # type: ignore[arg-type]
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/kb/documents/{doc_id}")
def kb_delete_document(doc_id: str) -> dict:
    """Remove a document's chunks and manifest entry from the knowledge base."""
    if "vectorstore" not in state:
        raise HTTPException(status_code=503, detail="Vector store not loaded.")
    removed = kb_service.delete_document(state["vectorstore"], doc_id)
    if removed == 0:
        raise HTTPException(status_code=404, detail=f"No document with id {doc_id}.")
    return {"doc_id": doc_id, "removed_sections": removed}


# ---------------------------------------------------------------------------
# Word exports — the frontend posts a report/draft back and gets a .docx
# ---------------------------------------------------------------------------

def _docx_response(data: bytes, filename: str) -> Response:
    return Response(
        content=data,
        media_type=DOCX_MIME,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/export/analysis")
def export_analysis(report: PreBidAnalysis) -> Response:
    """Render a pre-bid analysis report as a downloadable Word document."""
    stem = Path(report.rfp_filename).stem or "analysis"
    return _docx_response(prebid_report_to_docx_bytes(report), f"{stem}_analysis.docx")


@app.post("/export/proposal")
def export_proposal(draft: ProposalDraft) -> Response:
    """Render a proposal draft as a downloadable Word document."""
    stem = Path(draft.rfp_filename).stem or "proposal"
    return _docx_response(proposal_to_docx_bytes(draft), f"{stem}_proposal.docx")


# ---------------------------------------------------------------------------
# Workspace — bid pipeline tracker
# ---------------------------------------------------------------------------

class BidCreate(BaseModel):
    """Request body for adding a bid to the workspace."""
    rfp_filename: str
    status: str = "analyzed"
    analysis: dict | None = None


class BidUpdate(BaseModel):
    """Request body for updating a bid's pipeline status."""
    status: str


@app.get("/workspace/bids", response_model=list[WorkspaceBid])
def workspace_list_bids() -> list[WorkspaceBid]:
    """List all tracked RFP bids, newest first."""
    return workspace_service.list_bids()


@app.post("/workspace/bids", response_model=WorkspaceBid)
def workspace_add_bid(body: BidCreate) -> WorkspaceBid:
    """Add a new RFP bid to the workspace pipeline."""
    return workspace_service.add_bid(body.rfp_filename, body.status, body.analysis)


@app.patch("/workspace/bids/{bid_id}", response_model=WorkspaceBid)
def workspace_update_bid(bid_id: str, body: BidUpdate) -> WorkspaceBid:
    """Update a bid's pipeline status (e.g., mark as won, drafting, reviewing)."""
    bid = workspace_service.update_bid_status(bid_id, body.status)
    if bid is None:
        raise HTTPException(status_code=404, detail=f"No bid with id {bid_id}.")
    return bid


@app.delete("/workspace/bids/{bid_id}")
def workspace_delete_bid(bid_id: str) -> dict:
    """Remove a bid from the workspace."""
    if not workspace_service.delete_bid(bid_id):
        raise HTTPException(status_code=404, detail=f"No bid with id {bid_id}.")
    return {"bid_id": bid_id, "deleted": True}


# ---------------------------------------------------------------------------
# Chat history — save and reload Ask-page conversations
# ---------------------------------------------------------------------------

class ChatSaveRequest(BaseModel):
    """Create or update a chat session with the current conversation."""
    messages: list[dict] = Field(default_factory=list)
    session_id: str | None = None
    title: str | None = None


@app.get("/chat/sessions", response_model=list[ChatSessionSummary])
def chat_list_sessions() -> list[ChatSessionSummary]:
    """List saved chat sessions, most recently updated first."""
    return chat_service.list_sessions()


@app.get("/chat/sessions/{session_id}", response_model=ChatSession)
def chat_get_session(session_id: str) -> ChatSession:
    """Load a full chat session by id."""
    session = chat_service.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"No chat session {session_id}.")
    return session


@app.post("/chat/sessions", response_model=ChatSession)
def chat_save_session(body: ChatSaveRequest) -> ChatSession:
    """Create a new chat session or update an existing one (by session_id)."""
    return chat_service.save_session(body.messages, body.session_id, body.title)


@app.delete("/chat/sessions/{session_id}")
def chat_delete_session(session_id: str) -> dict:
    """Delete a saved chat session."""
    if not chat_service.delete_session(session_id):
        raise HTTPException(status_code=404, detail=f"No chat session {session_id}.")
    return {"session_id": session_id, "deleted": True}


# ---------------------------------------------------------------------------
# Admin — control the active LLM provider at runtime
# ---------------------------------------------------------------------------

class LLMConfigUpdate(BaseModel):
    """Runtime overrides for the LLM. All fields optional."""
    provider: str | None = None
    model: str | None = None
    local_base_url: str | None = None


@app.get("/admin/llm")
def admin_get_llm() -> dict:
    """Return the current LLM provider config and which providers have keys."""
    return config.admin_config()


@app.post("/admin/llm")
def admin_set_llm(body: LLMConfigUpdate) -> dict:
    """Apply runtime LLM overrides (provider / model / local URL)."""
    try:
        return config.set_admin_config(body.provider, body.model, body.local_base_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/admin/llm/test")
def admin_test_llm() -> dict:
    """Test the active provider with a tiny call; surfaces key/package/URL issues."""
    cfg = config.admin_config()
    try:
        llm = config.get_llm()
        llm.invoke("ping")
        return {"ok": True, "provider": cfg["provider"], "model": cfg["model"]}
    except Exception as e:
        return {"ok": False, "provider": cfg["provider"], "error": str(e)}
