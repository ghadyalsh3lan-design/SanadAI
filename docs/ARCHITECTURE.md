# SanadAI / RFP Intelligence — Architecture

This document describes two views of the system:

1. **System architecture** — the components, how they talk, and where data lives.
2. **RAG architecture** — the ingestion and query pipelines in detail.

---

## 1. System Architecture

### 1.1 High-level diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          BROWSER (React + Vite SPA)                        │
│                                                                            │
│  Sidebar nav → pages:                                                      │
│   Dashboard · Knowledge base · Analyze · Draft · Ask · Workspace ·         │
│   About · Admin                                                            │
│                                                                            │
│  api.js  (fetch client → VITE_API_URL, default http://127.0.0.1:8000)      │
└───────────────────────────────┬────────────────────────────────────────────┘
                                 │ HTTP / JSON (CORS)
                                 ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                        FastAPI backend  (src/api/main.py)                  │
│                                                                            │
│  Q&A         /query          /evaluate                                     │
│  RFP library /rfps  /rfps/{f}/analyze  /rfps/{f}/draft[/section]           │
│  Analyze/Draft /analyze-rfp  /draft-proposal  /export/{analysis,proposal} │
│  KB mgmt     /kb/documents  /kb/stats                                      │
│  Workspace   /workspace/bids ...                                           │
│  Chat        /chat/sessions ...                                            │
│  Admin       /admin/llm  /admin/llm/test                                   │
└───────┬───────────────┬───────────────┬───────────────┬───────────────────┘
        │               │               │               │
        ▼               ▼               ▼               ▼
┌─────────────┐ ┌──────────────┐ ┌─────────────┐ ┌────────────────────────┐
│ Ingestion   │ │ Retrieval    │ │ Generation  │ │ Domain services        │
│ parser      │ │ vector_store │ │ generator   │ │ analysis/pre_bid       │
│ chunker     │ │  (Chroma)    │ │ verifier    │ │ drafting/proposal      │
│ kb_service  │ │  embeddings  │ │ judge       │ │ drafting/export (docx) │
│ rfp_service │ │  reranker    │ │             │ │ workspace_service      │
│             │ │              │ │             │ │ chat_service           │
└──────┬──────┘ └──────┬───────┘ └──────┬──────┘ └───────────┬────────────┘
       │               │                │                    │
       ▼               ▼                ▼                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                              Storage / external                            │
│  Chroma (./chroma_db)        — vector index (KB + incoming RFP chunks)     │
│  data/company_kb/            — uploaded KB files + _kb_manifest.json       │
│  data/incoming_rfps/         — saved incoming RFP files                    │
│  data/workspace.json         — tracked bids (+ full saved analysis)        │
│  data/chat_sessions.json     — Ask conversations                           │
│  HuggingFace models (local)  — embeddings + cross-encoder reranker         │
│  LLM provider (config.get_llm) — Groq | OpenAI | Anthropic | Gemini | Local│
└──────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Layers and responsibilities

| Layer | Modules | Responsibility |
|-------|---------|----------------|
| Frontend | `frontend/src/pages/*`, `components/*`, `api.js` | UI, calls the API; no business logic |
| API | `src/api/main.py` | HTTP endpoints, request/response models, orchestration |
| Ingestion | `src/ingestion/{parser,chunker,kb_service,rfp_service}.py` | Parse → normalize → chunk → index documents |
| Retrieval | `src/retrieval/vector_store.py` | Embeddings, Chroma, similarity search, cross-encoder rerank |
| Generation | `src/generation/{generator,verifier,judge}.py` | Grounded answers, verification, LLM-as-judge |
| Analysis | `src/analysis/pre_bid.py` | Requirement coverage + bid/no-bid recommendation |
| Drafting | `src/drafting/{proposal,export}.py` | Section-by-section proposal draft, Word export |
| Workspace/Chat | `src/workspace/workspace_service.py`, `src/chat/chat_service.py` | Bid tracking, chat history (JSON persistence) |
| Config | `src/config.py` | `.env` loading, LLM factory + runtime override, date prefix |

### 1.3 LLM provider abstraction

All generation code calls `config.get_llm()` — never a provider SDK directly.

```
caller → config.get_llm(model=None)
              │   provider = runtime override  ▶ or LLM_PROVIDER env ▶ or "groq"
              ▼
   groq | anthropic | openai | gemini | local   (lazy import of the one in use)
              │
              ▼  LangChain BaseChatModel (ChatGroq / ChatOpenAI / ...)
```

The Admin page (`/admin`) sets an in-memory override (`config._runtime`) for
provider/model/local-URL at runtime; it resets to `.env` on restart. API keys live
only in `.env`.

### 1.4 Persistence model

No database — state is files:
- **Chroma** (`./chroma_db`): the only "heavy" store; holds embedded chunks with
  metadata (`source`, `source_type`, `doc_id`, `page`, `chunk_index`, `doc_type`).
- **JSON files** under `data/`: KB manifest, workspace bids, chat sessions.
- **Disk**: original KB and incoming-RFP files (so RFPs can be re-analyzed/re-indexed).

---

## 2. RAG Architecture

The pipeline has two halves: **ingestion** (offline, when documents are uploaded)
and **query** (online, when a user asks a question).

### 2.1 Ingestion pipeline

```
upload (PDF/DOCX/PPTX/MD/TXT)
   │
   ▼  parser.parse_file              one Document per page/slide/file;
   │   + tables → Markdown            tables rendered inline as pipe tables
   ▼  parser.normalize_text          strip "P a g e x|y" footers, TOC dot
   │                                  leaders; de-hyphenate; collapse whitespace
   ▼  chunker.chunk_documents        RecursiveCharacterTextSplitter
   │   size=900, overlap=150          + drop boilerplate (too short / mostly
   │   _is_useful() filter            separators); assign chunk_index
   ▼  vector_store embeddings        sentence-transformers
   │                                  paraphrase-multilingual-MiniLM-L12-v2
   │                                  (384-dim, L2-normalized, multilingual incl. Arabic)
   ▼  Chroma (cosine space)          add_chunks → ./chroma_db
        metadata: source, source_type(company_kb|incoming_rfp), doc_id, page, doc_type
```

- **Company KB** goes in via `kb_service.ingest_file` (tagged `company_kb` + a
  `doc_type` category) and tracked in `_kb_manifest.json`.
- **Incoming RFPs** go in via `rfp_service.index_rfp` (tagged `incoming_rfp`);
  re-uploads delete the old chunks for that filename first to avoid duplicates.

### 2.2 Query pipeline (Ask)  — two-stage retrieval + grounded generation

```
question (+ optional filters, chat history)
   │
   ▼  condense_question()             follow-ups → standalone question using
   │   (only if history present)       the last ~6 turns  [history-aware]
   │
   ▼  STAGE 1 — bi-encoder recall      vector_store.search_with_scores(k = K*4)
   │   filter = _build_kb_filter(       (company_kb [+ incoming_rfp], optional
   │     doc_types, sources, rfps)       doc_type / source narrowing)
   │
   ▼  relevance gate                   keep score ≥ 0.4 (DEFAULT_RELEVANCE_THRESHOLD)
   │   (relaxed to 0 when the user      → empty result ⇒ refuse, don't hallucinate
   │    explicitly scopes to docs)
   │
   ▼  STAGE 2 — cross-encoder rerank   rerank() ms-marco-MiniLM-L-6-v2 scores
   │   re-orders by joint               (query, chunk) jointly; sigmoid → 0..1
   │   query–passage relevance          + per-page cap (max 2/page) → top K
   │   (score shown as "% match")
   │
   ▼  generate_answer()                LLM messages = [system grounding rules]
   │   prompt = system + history +       + prior turns (memory) + (context+question)
   │   grounded user msg                strict: answer only from context, flag
   │                                     passed deadlines, refuse if unsupported
   │
   ▼  Answer { text, sources[], refused }
        sources carry source/page/preview/relevance(% match)
```

Key properties:
- **Refusal over hallucination**: the relevance gate makes "no good context" a
  first-class outcome — the system answers a fixed refusal string instead of
  guessing.
- **Memory**: recent turns are both condensed (for retrieval) and replayed as chat
  messages (for generation).
- **Date awareness**: `config.date_prefix()` prepends today's date to every prompt.

### 2.3 Evaluation path (/evaluate, LLM-as-judge)

```
question + answer
   │
   ▼  _retrieve_reranked()   ← SAME two-stage retrieval as /query
   │                            (so the judge sees the answer's real context)
   ▼  judge.evaluate_answer()  LLM scores: faithfulness, relevance, completeness,
        defensive JSON parse    groundedness, citation quality, hallucination
        (+ regex fallback)      → metric bars + summary + recommendations
```

### 2.4 Analyze (pre-bid) and Draft reuse the same retrieval

- **Analyze** (`analysis/pre_bid.py`): extract requirements → per-requirement
  retrieve + rerank → coverage assessment; plus a broad KB retrieval feeding one
  structured **bid/no-bid recommendation** (Bid / No Bid / Bid with Risks, 8-area
  detail). Exportable to Word.
- **Draft** (`drafting/proposal.py`): per-section retrieval (`search_relevant`) →
  grounded section prose with citations; flags ungrounded sections.

### 2.5 Tunable parameters (where to change them)

| Parameter | Value | Location |
|-----------|-------|----------|
| Embedding model | paraphrase-multilingual-MiniLM-L12-v2 | `vector_store.DEFAULT_EMBEDDING_MODEL` |
| Reranker model | cross-encoder/ms-marco-MiniLM-L-6-v2 | `vector_store.DEFAULT_RERANK_MODEL` |
| Chunk size / overlap | 900 / 150 | `chunker.DEFAULT_CHUNK_SIZE/OVERLAP` |
| Relevance threshold | 0.4 | `vector_store.DEFAULT_RELEVANCE_THRESHOLD` |
| Top-k (Ask) | 1–20 (UI), over-fetch K*4 | `Ask.jsx`, `main.py` query |
| Per-page citation cap | 2 | `main.py QUERY_MAX_PER_PAGE` |

### 2.6 Benchmarking

`benchmarks/` evaluates each step against a self-contained golden fixture
(`benchmarks/sample_kb/` + `golden_qa.json`):

```
chunking   → chunk counts/sizes              (no LLM)
retrieval  → hit@k, MRR, precision@k         basic vs reranked (no LLM)
generation → faithfulness, relevance         (LLM judge)
rag        → rubric table across 4 setups:   LLM Only | Basic RAG |
             Faithfulness/Relevance/Precision  Optimized RAG | RAG + reranking
```
Results are written as CSV to `benchmarks/results/`.

---

## 3. Request lifecycle example — "Who is the RFP contact?"

```
Ask.jsx → POST /query {question, k, filters, history}
  → condense_question() (no-op for first turn)
  → search_with_scores(k=12, filter=company_kb[+rfp])      [bi-encoder]
  → drop score < 0.4
  → rerank() → top 3, ≤2 per page                          [cross-encoder]
  → generate_answer(question, chunks, history)             [config.get_llm()]
  → { answer:"Faiza Hussain …", sources:[{source,page,relevance}], refused:false }
Ask.jsx renders answer (Markdown) + source cards (% match) + Evaluate button
```
