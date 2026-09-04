# SanadAI

**سند · your proposal co-pilot** — a retrieval-augmented (RAG) assistant that helps
consulting teams decide whether to bid on an RFP and draft the response, with every
answer grounded in the company's own documents.

*Sanad (سند)* means "support" or "pillar" — the system is the proposal team's backing
for every bid.

**Team:** Munther Alghamdi · Osama Alghamdi · Hessa Abdullatif · Ghady Alshalan
**Bootcamp:** Saudi Digital Academy — AI Engineering · RCP #8 · 3 weeks

---

## What it does

| Use case | Example | Output |
|---|---|---|
| Question answering | "What experience do we have in AI for government?" | Grounded answer with citations + % match |
| Capability lookup | "Do we have LLMOps experience?" | Yes/no with evidence |
| Pre-bid analysis | (select a saved RFP) | Bid/No-Bid recommendation + coverage table + clarifying questions |
| Proposal drafting | (select a saved RFP) | Multi-section draft, grounded + cited, Word export |
| Knowledge base | (upload past work) | A searchable, typed company library |
| Bid tracking | (save an analysis) | Workspace pipeline with win-rate stats |

Two principles run through all of it: **citations are mandatory**, and the system
**refuses rather than hallucinates** when retrieval is weak.

---

## Highlights

- **Multi-provider LLM** — Groq · OpenAI · Anthropic · Gemini · Local (any
  OpenAI-compatible server). Switch live from the **Admin** page; keys stay in `.env`.
- **Two-stage retrieval** — bi-encoder recall → relevance gate → **cross-encoder
  reranker**, so the chunk that actually answers the question ranks first.
- **Bid / No-Bid recommendation** — confidence, strengths, risks, missing
  requirements, an 8-area assessment, and a summary, on top of requirement coverage.
- **Conversational Ask** — chat memory, history-aware follow-ups, filters
  (category / document / incoming RFP), per-answer **LLM-as-judge** evaluation, and
  suggested questions.
- **Reproducible benchmarks** — per-RAG-step scripts with a self-contained golden
  fixture, results saved to CSV.

---

## Architecture

Full diagrams (system + RAG pipelines) are in **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**.
Summary:

```
Company KB + Incoming RFPs
        │  parse(+tables) → normalize → chunk(900/150) → embed → Chroma
        ▼
   [ Retrieval ]   bi-encoder top-k → relevance gate (≥0.4) → cross-encoder rerank
        ▼
   [ Generation ]  grounded answer + citations (+ chat memory, date-aware) or honest refusal
        ▼
   Answer · Pre-bid report · Proposal draft · LLM-judge scores

   FastAPI backend  ⇄ REST ⇄  React frontend (Vite + Tailwind)
```

---

## Tech stack

| Layer | Choice |
|---|---|
| Language | Python 3.13 |
| Orchestration | LangChain |
| Vector store | Chroma (local, cosine space) |
| Embeddings | Sentence Transformers `paraphrase-multilingual-MiniLM-L12-v2` (multilingual incl. Arabic, normalized) |
| Reranker | Cross-encoder `ms-marco-MiniLM-L-6-v2` |
| LLM | Multi-provider via `config.get_llm()` — Groq / OpenAI / Anthropic / Gemini / Local |
| API | FastAPI + uvicorn |
| Frontend | React + Vite + Tailwind CSS (react-markdown) |
| Validation | Pydantic |
| Parsing | pymupdf, python-docx, python-pptx (tables → Markdown) |
| Evaluation | retrieval hit@k/MRR/precision · LLM-as-judge · RAGAS · `benchmarks/` |

---

## Project statistics

| Metric | Value |
|---|---|
| Backend Python (src/) | ~3,600 LOC across 24 modules |
| Frontend (React) | ~2,900 LOC across 9 pages |
| Evaluation + benchmarks | ~780 LOC |
| Total Python | ~4,700 LOC |
| REST endpoints | 29 |
| Frontend pages | Dashboard · Knowledge base · Analyze · Draft · Ask · Workspace · About · Admin · Setup |
| LLM providers supported | 5 (Groq, OpenAI, Anthropic, Gemini, Local) |
| Golden QA sets | 20 pairs (real KB) + 12 pairs (benchmark fixture) |
| Dev/test notebooks | 13 |
| Judge metrics | 6 (faithfulness, relevance, completeness, groundedness, citation quality, hallucination) |

---

## Setup

```bash
git clone https://github.com/Mun145/rfp-intelligence.git
cd rfp-intelligence

# Backend
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .
cp .env.example .env                 # then set LLM_PROVIDER + the matching key

# Frontend (needs Node.js 18+)
cd frontend && npm install && cd ..
```

`.env` essentials:
```
LLM_PROVIDER=groq                    # groq | openai | anthropic | gemini | local
GROQ_API_KEY=...                     # (or the key for your chosen provider)
# For local (Ollama / LM Studio / llama.cpp / vLLM):
# LLM_PROVIDER=local
# LOCAL_BASE_URL=http://localhost:11434/v1
```

## Running

```bash
# 1. (optional) Index a company knowledge base from the CLI
python scripts/index_corpus.py

# 2. Start the API
uvicorn src.api.main:app --reload          # http://127.0.0.1:8000

# 3. Start the SanadAI frontend (separate terminal)
cd frontend && npm run dev                 # http://localhost:5173
```

Open **http://localhost:5173**. With an empty knowledge base, SanadAI shows a
first-run setup screen to upload documents (then lands on the About page);
otherwise it opens on the dashboard. Switch LLM provider any time from **Admin**.

---

## API endpoints (29 total)

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Liveness probe |
| `POST` | `/query` | Grounded Q&A — filters, top-k, chat memory, reranked retrieval |
| `POST` | `/evaluate` | LLM-as-judge scoring of an answer (6 metrics) |
| `POST` | `/analyze-rfp` · `/draft-proposal` | Pre-bid analysis · multi-section draft (upload) |
| `GET`/`POST`/`DELETE` | `/rfps` · `/rfps/{f}` | Incoming-RFP library |
| `POST` | `/rfps/{f}/analyze` · `/rfps/{f}/draft[/section]` | Analyze / draft a saved RFP |
| `GET` | `/kb/documents` · `/kb/stats` | List documents · dashboard stats |
| `POST`/`DELETE` | `/kb/documents[/{id}]` | Upload / remove a KB document |
| `POST` | `/export/analysis` · `/export/proposal` | Download report/draft as Word (.docx) |
| `GET`/`POST`/`PATCH`/`DELETE` | `/workspace/bids[...]` | Bid pipeline tracking |
| `GET`/`POST`/`DELETE` | `/chat/sessions[...]` | Ask chat history |
| `GET`/`POST` | `/admin/llm` · `/admin/llm/test` | Runtime LLM provider control |

Interactive docs at `http://127.0.0.1:8000/docs`.

---

## Evaluation & benchmarks

**Quick eval** (against the real golden set):
- Retrieval (no LLM): `python -m evaluation.retrieval_eval` → hit@k / MRR.
- End-to-end setups: `python scripts/run_evaluation.py` (LLM-as-judge + optional RAGAS).

**Benchmark suite** (`benchmarks/`, self-contained fixture in `benchmarks/sample_kb/`
+ `benchmarks/golden_qa.json`, results → CSV):

```bash
python benchmarks/benchmark_chunking.py     # chunk counts/sizes (no LLM)
python benchmarks/benchmark_retrieval.py    # hit@k, MRR, precision@k: basic vs reranked (no LLM)
python benchmarks/benchmark_generation.py   # faithfulness + relevance (LLM judge)
python benchmarks/benchmark_rag.py          # the rubric table (4 setups)
```

Representative `benchmark_rag.py` output (local model, sample fixture):

| Setup | Faithfulness | Relevance | Retrieval Precision | Notes |
|---|---|---|---|---|
| LLM Only | 1.5 | 9.0 | N/A | Hallucination risk |
| Basic RAG | 9.42 | 9.75 | 0.43 | Baseline |
| Optimized RAG | 9.58 | 10.0 | 0.61 | Improved |
| RAG + reranking | 9.75 | 9.92 | 0.61 | Advanced |

RAG lifts faithfulness from ~1.5 (LLM alone can't know the docs) to ~9.4+; larger
chunks raise retrieval precision.

---

## Project layout

```
rfp-intelligence/
├── src/
│   ├── ingestion/      parser (table-aware + normalize), chunker, kb_service, rfp_service
│   ├── retrieval/      vector_store (cosine search, relevance gate, cross-encoder rerank)
│   ├── generation/     generator (memory), verifier, judge
│   ├── analysis/       pre_bid (coverage + bid/no-bid)
│   ├── drafting/       proposal, export (.docx)
│   ├── workspace/      workspace_service (bid tracking)
│   ├── chat/           chat_service (Ask history)
│   ├── config.py       .env + LLM factory (runtime override) + date prefix
│   └── api/            main.py (FastAPI, 29 endpoints)
├── frontend/           SanadAI React app (Vite + Tailwind), 9 pages
├── evaluation/         golden_qa.json, llm_judge, retrieval_eval
├── benchmarks/         per-step benchmarks + sample_kb fixture + golden_qa.json
├── scripts/            index_corpus, run_evaluation
├── docs/               ARCHITECTURE.md
└── data/company_kb/    capability docs (tracked) + real proposals (ignored)
```

---

## Design principles

- **Citations are non-negotiable** — every grounded claim points to a source chunk.
- **Refusal over hallucination** — a relevance gate (cosine ≥ 0.4) means weak
  retrieval yields an honest "I don't know," not a guess.
- **User decides, system informs** — pre-bid surfaces evidence and a recommendation
  to weigh, not an order.
- **Grounded citations** — pre-bid, drafting, and Q&A cite the *retrieved* document,
  never an LLM-invented filename.
- **One module, one responsibility** — ingestion, retrieval, generation, analysis,
  drafting, workspace, and chat are separate and individually testable.
- **Provider-agnostic** — all generation goes through `config.get_llm()`, so the LLM
  is swappable at runtime without code changes.
