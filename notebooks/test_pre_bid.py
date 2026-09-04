"""
Integration test for the pre-bid analysis module.

Indexes one of the sample RFPs from data/incoming_rfps/ into a temporary
vector store, then runs analyze_rfp() against the company KB.

Usage:
    python notebooks/test_pre_bid.py
"""
import sys
from pathlib import Path

RFP_DIR = Path("data/incoming_rfps")
CHROMA_DIR = "./chroma_db"


def find_rfp() -> Path:
    for ext in (".pdf", ".docx", ".pptx", ".md", ".txt"):
        matches = list(RFP_DIR.glob(f"*{ext}"))
        if matches:
            return matches[0]
    print(f"ERROR: No RFP files found in {RFP_DIR}")
    sys.exit(1)


def main() -> None:
    if not Path(CHROMA_DIR).exists():
        print(f"ERROR: No vector store at {CHROMA_DIR}.")
        print("Run `python scripts/index_corpus.py` first.")
        sys.exit(1)

    from src.retrieval.vector_store import load_vector_store
    from src.ingestion.parser import parse_file
    from src.analysis.pre_bid import analyze_rfp

    rfp_path = find_rfp()
    print(f"Using RFP: {rfp_path.name}\n")

    print("Loading company KB vector store...")
    vs = load_vector_store(persist_dir=CHROMA_DIR)

    print("Parsing RFP...")
    documents = parse_file(rfp_path, source_type="incoming_rfp")
    rfp_text = "\n\n".join(doc.page_content for doc in documents)
    print(f"Extracted {len(rfp_text):,} characters from {len(documents)} page(s).\n")

    print("Running pre-bid analysis (this will take ~30–60 seconds)...\n")
    report = analyze_rfp(rfp_text, rfp_path.name, vs)

    print("=" * 60)
    print(f"COVERAGE SUMMARY for: {report.rfp_filename}")
    print("=" * 60)
    s = report.coverage_summary
    print(f"  Fully covered:     {s.fully_covered}")
    print(f"  Partially covered: {s.partially_covered}")
    print(f"  Not covered:       {s.not_covered}")
    print(f"  Total requirements: {len(report.requirements)}\n")

    print("REQUIREMENTS:")
    print("-" * 60)
    for r in report.requirements:
        icon = {"fully_covered": "✓", "partially_covered": "~", "not_covered": "✗"}.get(r.coverage, "?")
        print(f"{icon} [{r.coverage}]")
        print(f"  Req:      {r.requirement}")
        print(f"  Evidence: {r.evidence[:120]}...")
        if r.source:
            print(f"  Source:   {r.source}")
        print()

    print("CLARIFYING QUESTIONS:")
    print("-" * 60)
    for q in report.clarifying_questions:
        print(f"[{q.severity.upper()}] {q.question}")

    print("\nTest completed successfully.")


if __name__ == "__main__":
    main()
