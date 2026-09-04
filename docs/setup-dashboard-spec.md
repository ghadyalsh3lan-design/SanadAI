# Spec — KB Setup Page + Dashboard

Status: agreed 2026-06-13. Persona: "Sami", a semi-technical proposal manager who
will never open a terminal.

## 1. Scope
First-run **Setup** page (build the library via the UI, no CLI) and a
**Dashboard/Home** with document management and a KB-strength meter. Not the
proposal drafter — that's a separate effort.

## 2. Navigation
Today: two bare tabs (Q&A, RFP Analyzer); KB must be pre-built via CLI.
Proposed: a left sidebar with four destinations + smart first-run routing.

- 🏠 Home (Dashboard)
- 📚 Knowledge Base (manage documents)
- 📄 Analyze RFP
- 💬 Ask a Question

Routing: KB empty → land on Setup; KB ready → land on Home.

## 3. First-run Setup ("Build your library")
Trigger: KB empty. The PM picks a document type, then uploads files of that type,
and repeats. The type drives the metadata tag (no fragile auto-classification).

| Bucket (label) | doc_type |
|---|---|
| Past proposals & RFP responses | proposal |
| Capability statements | capability |
| Case studies / project sheets | case_study |
| CVs / resumes | cv |
| Certifications (ISO, partner) | certification |
| Partners / vendors / teaming | partner |
| Company overview & boilerplate | overview |
| Policies (security, QA, HSE) | policy |

Flow: choose type → upload → **Add to knowledge base** → progress → success
("I learned from N documents") → Home.

## 4. Home / Dashboard
1. Summary line — "N documents · M sections · updated <date>".
2. Document table — name, type, sections, [delete].
3. KB-strength meter — count per category; categories with 0 docs flagged "thin".
4. Two primary buttons — Analyze a new RFP · Ask a question.

## 5. Knowledge Base manager
Same table + an "Add documents" uploader (reuses §3). How the library grows.

## 6. KB-strength meter
v1 (shipped): count documents per doc_type; 0-doc categories flagged "thin".
Deterministic, self-explaining.
v2 (later): run fixed capability probe questions through retrieval; categories
whose top score stays below the 0.4 gate are "thin".

## 7. Under-the-hood changes (respecting locked design)
- Add `doc_type` to chunk metadata (set after parse, propagates via chunker — no
  parser/chunker change).
- In-app incremental indexing: `add_chunks()` adds to the live store instead of
  the CLI's rmtree+rebuild. Same in-process instance the app searches → no Chroma
  file-lock conflict.
- Delete by document: remove a doc's chunks by `doc_id`.
- `get_or_create_vector_store()` so a first-run user starts from an empty,
  writable store instead of an error.
- Manifest (`data/company_kb/_kb_manifest.json`): filename, doc_type, date,
  doc_id, chunk_count — powers the document table; bootstrapped from the existing
  store via `sync_manifest_from_store()`.
- New module `src/ingestion/kb_service.py` orchestrates this. Parser, chunker,
  vector_store, source_type, citations, refusal, Pydantic all unchanged.

## 8. Build phases
- P1 — Setup page: uploader + doc_type + incremental add + manifest.
- P2 — Dashboard: table + delete + summary + v1 strength meter.
- P3 — Polish: sidebar nav, plain-language pass, clickable citations.

## 9. Decisions
1. Shared KB (no auth) for the 3-person firm. **Agreed.**
2. Originals live in `data/company_kb/`. **Agreed.**
3. Sensitive docs (pricing/rate cards): deferred past v1.
4. Bulk folder/zip upload: deferred past v1 (one type-batch at a time).
