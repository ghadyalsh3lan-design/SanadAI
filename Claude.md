# RFP Intelligence System — Claude Code Context

You are helping a 3-person team finish a 3-week SDA AI Engineering bootcamp capstone. This file gives you everything you need to know about the project. Read it fully before responding to any task.

---

## Project Snapshot

A retrieval-augmented generation (RAG) system for a consulting firm that responds to RFPs frequently across AI, data, cloud, and enterprise training engagements.

The system helps proposal writers across the full workflow: analyze incoming RFPs (pre-bid analysis), answer questions about company capabilities (Q&A), and (ambitious goal) draft full RFP responses.

**Team:** Munther Alghamdi, Osama Alghamdi, Hessa Abdullatif, Ghady Alshalan (Hessa has been less active; treat the build team as 3 people).

**Timeline:** 3 weeks total. Week 1 = MVP foundation. Week 2 = MVP completion + checkpoint. Week 3 = ambitious goals only if MVP is stable.

**Environment:** Windows 11, PowerShell, Python 3.13, VS Code.

---

## Architecture

Two knowledge sources -> one RAG pipeline -> two output modes.

**Knowledge sources:**
- **Company Knowledge Base** — past RFPs, capability statements, case studies, credentials, resumes, methodology docs (`source_type="company_kb"`)
- **Incoming RFP** — the document being analyzed or responded to (`source_type="incoming_rfp"`)

**Pipeline:**
1. **Ingestion** — parse multiple formats, chunk with metadata, embed with Sentence Transformers, store in Chroma
2. **Retrieval** — top-k similarity search with metadata filtering by `source_type`
3. **Generation** — grounded LLM answer with mandatory citations and honest refusal
4. **Verification (optional)** — second LLM call checks faithfulness + completeness
5. **Analysis (MVP)** — pre-bid analysis: requirement coverage + clarifying questions
6. **Drafting (ambitious)** — full proposal assembly, one section at a time

**Output modes:**
- Short Q&A answer with citations
- Pre-bid analysis report (coverage table + clarifying questions)
- Full proposal draft (ambitious only)

---

## Tech Stack (locked, do not change)

- Python 3.13
- LangChain (orchestration)
- Chroma (vector store, local persistence at `./chroma_db`)
- Sentence Transformers `all-MiniLM-L6-v2` (embeddings, local)
- Groq + Llama 3.3 70B via `langchain-groq` (model id `llama-3.3-70b-versatile`)
- FastAPI + uvicorn (API)
- Pydantic (validation, structured outputs)
- pymupdf, python-docx, python-pptx (document parsing)
- RAGAS (evaluation)

Reasons these are locked: they're chosen, working, and learned. Do not propose alternatives unless a hard incompatibility forces it.

---

## Repository Layout

```
rfp-intelligence/
├── CLAUDE.md
├── README.md
├── requirements.txt
├── pyproject.toml                  # pip install -e .
├── .env                            # GROQ_API_KEY, gitignored
├── data/{company_kb,incoming_rfps} # gitignored
├── src/
│   ├── __init__.py                 # KEEP NEARLY EMPTY (circular import danger)
│   ├── config.py                   # load_dotenv() at module level + accessors
│   ├── ingestion/
│   │   ├── parser.py
│   │   └── chunker.py
│   ├── retrieval/
│   │   └── vector_store.py
│   ├── generation/
│   │   ├── generator.py
│   │   └── verifier.py             # NEW (MVP)
│   ├── analysis/
│   │   └── pre_bid.py              # NEW (MVP)
│   ├── drafting/
│   │   └── proposal.py             # NEW (ambitious)
│   └── api/
│       └── main.py
├── scripts/
│   ├── index_corpus.py
│   └── run_evaluation.py
├── evaluation/
│   ├── golden_qa.json
│   └── llm_judge.py
├── notebooks/                      # ad-hoc test scripts
└── chroma_db/                      # gitignored
```

---

## Design Decisions (locked, do not redesign without flagging)

1. **Parser and chunker are separate modules.** They change for different reasons.
2. **Schema metadata propagates parser -> chunker -> vector store.** Every chunk has `doc_id`, `source`, `source_type`, `section`, `tags`, `chunk_index`, plus parser-added fields like `page`.
3. **`source_type` is critical.** It distinguishes `company_kb` from `incoming_rfp`. Retrieval filters by it so company KB queries don't pull from incoming RFPs and vice versa.
4. **Vector store has both `index_chunks` (write) and `load_vector_store` (read).** FastAPI uses the read path at startup via the lifespan hook so it doesn't re-embed on every request.
5. **Generator returns a Pydantic `Answer` with `answer`, `sources: list[Source]`, `refused: bool`.** Callers never parse strings to detect refusal.
6. **Strict grounding prompt.** Generator instructs the LLM to respond exactly "I don't have enough information to answer that based on the provided documents." when context is insufficient. Refusal detection is exact-string match.
7. **Refused responses have empty `sources`.** Don't cite sources alongside "I don't know."
8. **Env loading lives in `src/config.py`.** `src/__init__.py` stays empty. Files that need env explicitly `from src import config` at the top.
9. **`POST /query` includes an optional `verify: bool` field, default false.** When true, the answer is checked by the verifier and the response includes a `verification` block with `faithful`, `complete`, `missed_points`, `flagged_claims`.
10. **Pre-bid analysis returns one combined report.** Coverage table + clarifying questions in a single response. No recommendation field — the user is always the decision-maker.
11. **Clarifying questions have severity tags:** `blocker`, `important`, `nice-to-clarify`.

---

## Coding Standards (enforce)

- Type hints on all public functions.
- Pydantic models for any structured data crossing module boundaries.
- One file, one responsibility.
- Private helpers prefix with `_`.
- Public functions have docstrings with Args, Returns, Raises.
- Never parse error/state from strings. Use structured fields.
- No scattered `load_dotenv()` — centralize via `src/config.py`.
- Test scripts live in `notebooks/`, one per module.
- Tests follow the structure of existing `notebooks/test_*.py` files.

---

## Constraints

- **AI-assisted, not AI-generated.** Code in the repo must be defensible by a human team member in an interview. Don't produce code the team can't explain.
- **Don't expand scope.** If a task seems to require new features, list them and ask before adding.
- **Don't redesign locked modules.** If you find a bug, fix only the bug. Note other issues as TODO comments.
- **Show before applying.** When you propose changes, show what you'll change before doing it.
- **Commit cleanly.** Separate logical commits with clear messages. Don't mass-commit unrelated changes.

---

## Scope

### MVP (Weeks 1–2) — committed

1. Multi-format document ingestion (PDF, DOCX, PPTX, MD)
2. Chunking with metadata preservation
3. Embedding pipeline (Sentence Transformers)
4. Vector storage (Chroma) with metadata filtering
5. Top-k retrieval
6. Grounded LLM generation with mandatory citations and honest refusal
7. FastAPI `/health` and `/query` endpoints
8. Offline indexing script (`scripts/index_corpus.py`)
9. **Optional answer verifier on `/query` (`verify: true` flag)** — faithfulness + completeness
10. **Pre-bid analysis endpoint `/analyze-rfp`** — requirement coverage table + severity-tagged clarifying questions, evidence-only (no recommendation)
11. Golden QA set (20+ hand-built pairs)
12. RAGAS evaluation harness
13. **LLM-as-judge evaluation harness** — faithfulness + completeness on golden QA
14. Benchmark setups: (A) no-RAG, (B) basic RAG, (C) RAG + optimized chunking
15. Public GitHub repo + demo

### Ambitious (Week 3, only if MVP is stable at Week 2 checkpoint)

- `/draft-proposal` endpoint for full RFP drafting
- Per-section RAG generation
- Multi-section Markdown document assembly
- Streamlit demo UI

### Stretch (only if Ambitious is done)

- Always-on verification (verify default true)
- Hybrid search (keyword + semantic via BM25)
- Cross-encoder reranking
- Query rewriting
- Word/PDF export
- Feedback loop for retrieval

---

## Active Issues

- **Synthetic KB docs are now tracked.** `data/company_kb/IBTech_*.md` (5 generated
  English capability docs) are un-ignored so a fresh clone reproduces the index +
  benchmarks. The real Jouf proposal (Arabic) and the local `_kb_manifest.json` stay
  gitignored.
- **`ragas` not installed in the venv** (it's in requirements.txt). The eval harness
  is wired correctly (Groq LLM + local embeddings + real contexts) but skips with an
  install hint until `pip install ragas`. `python-multipart` was also missing and has
  been installed (required for the `/analyze-rfp` upload endpoint).
- **Relevance threshold is corpus-calibrated (0.4).** Set in
  `src/retrieval/vector_store.py` from this corpus (in-domain ≥0.58, out-of-domain
  ≤0.32). Re-calibrate with `notebooks/debug_retrieval.py` if the corpus or embedding
  model changes. Pre-bid uses the same gate, which biases toward `not_covered` on
  short/ambiguous requirement fragments — the safe direction for a bid/no-bid tool.

## Design Decisions Added This Session

- Parser extracts **tables** (DOCX/PDF/PPTX) as Markdown — RFP requirements and the
  KB's project/client tables live in tables and were previously dropped.
- Embeddings are L2-normalized and Chroma uses **cosine** space so relevance scores
  are thresholdable. Re-index after changing either.
- `search_relevant()` / `search_with_scores()` are the gated retrieval entry points;
  plain `search()` is kept for callers that don't need the gate.
- Pre-bid coverage **citations come from retrieved chunk metadata**, never the LLM.
- `evaluation/retrieval_eval.py` measures the retriever (hit@k + MRR) with no LLM.
- **Proposal drafting** (`src/drafting/proposal.py`, ambitious) does per-section RAG:
  one LLM call summarises the RFP, then each of 6 default sections retrieves KB
  evidence and is drafted grounded with citations. Sections with no evidence are
  flagged `grounded=False`.
- **Two relevance thresholds:** Q&A/pre-bid gate at 0.4 (refuse over hallucinate);
  drafting uses a lower 0.25 floor (generative, writer reviews, wants the best
  available evidence per section). Section retrieval queries are natural-language,
  not keyword bags — keyword bags embed poorly in MiniLM and miss the gate.
- **Frontend is now React** (`frontend/`, Vite + Tailwind, navy "SanadAI" theme) on the
  FastAPI backend; the Streamlit `app.py` has been **retired**. KB management
  (`src/ingestion/kb_service.py`) is exposed via API: `/kb/documents` (list/upload/delete)
  + `/kb/stats`; it indexes incrementally into the live store with a manifest, deletes by
  doc_id, and `sync_manifest_from_store` bootstraps from a CLI-built index.
- **Word export** (`src/drafting/export.py`) is served via `/export/analysis` and
  `/export/proposal` for the frontend's .docx downloads.
- **Run:** `uvicorn src.api.main:app --reload` + `cd frontend && npm run dev` (Node 18+).

---

## How to Help

For each task you're given:

1. Read this file fully.
2. Read the relevant existing modules before changing anything.
3. State your plan before editing.
4. Make the smallest change that solves the task.
5. If you find unrelated bugs, list them as TODOs in code comments and tell the user — don't fix them.
6. After changes, suggest a verification step (run a script, hit an endpoint, run a test).
7. Suggest a clean commit message.