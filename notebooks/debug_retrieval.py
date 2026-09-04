"""
Retrieval calibration / debugging helper.

Prints relevance scores for a set of probe queries so you can:
  - sanity-check what comes back for a given question, and
  - calibrate DEFAULT_RELEVANCE_THRESHOLD in src/retrieval/vector_store.py
    (look at the gap between real in-domain queries and out-of-domain ones).

Usage:
    python notebooks/debug_retrieval.py
    python notebooks/debug_retrieval.py "your custom question here"
"""
import sys

from src.retrieval.vector_store import (
    load_vector_store,
    search_with_scores,
    DEFAULT_RELEVANCE_THRESHOLD,
)

# Probe queries: a few in-domain, a few deliberately out-of-domain. The
# threshold should sit cleanly between the two groups' top scores.
IN_DOMAIN = [
    "What AI or machine learning services has IBTech delivered?",
    "What is IBTech's approach to project management?",
    "What cloud infrastructure experience does IBTech have?",
]
OUT_OF_DOMAIN = [
    "How do I bake chocolate chip cookies?",
    "What is the capital of France?",
]


def _probe(vs, query: str, k: int = 3) -> None:
    scored = search_with_scores(vs, query, k=k, filter={"source_type": "company_kb"})
    top = scored[0][1] if scored else 0.0
    gate = "PASS" if top >= DEFAULT_RELEVANCE_THRESHOLD else "REFUSE"
    print(f"[{gate}] top={top:.3f}  {query}")
    for doc, score in scored:
        print(f"    {score:.3f}  {doc.metadata.get('source', 'unknown')}")
    print()


def main() -> None:
    vs = load_vector_store()
    print(f"Relevance threshold: {DEFAULT_RELEVANCE_THRESHOLD}\n")

    if len(sys.argv) > 1:
        _probe(vs, " ".join(sys.argv[1:]))
        return

    print("=== In-domain (should PASS) ===")
    for q in IN_DOMAIN:
        _probe(vs, q)
    print("=== Out-of-domain (should REFUSE) ===")
    for q in OUT_OF_DOMAIN:
        _probe(vs, q)


if __name__ == "__main__":
    main()
