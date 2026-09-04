"""
Retrieval-quality evaluation for the RFP Intelligence System.

The LLM-judge (evaluation/llm_judge.py) measures the *generator*. This module
measures the *retriever* in isolation: given a golden question whose answer is
known to live in specific source document(s), does top-k retrieval actually
surface one of them?

It needs no LLM — only the vector store — so it is fast, free, and
deterministic. That makes it the cheapest credible signal that the retrieval
half of the pipeline works, and it isolates retrieval failures from generation
failures.

Metrics:
  - hit@k: fraction of questions where at least one retrieved chunk comes from
           an expected source document.
  - MRR:   mean reciprocal rank of the first correct source (1.0 if the top
           result is correct, 0.5 if the second, etc.).

Usage:
    python evaluation/retrieval_eval.py
    python evaluation/retrieval_eval.py --k 5
"""
import argparse
from typing import Any

from langchain_chroma import Chroma
from pydantic import BaseModel

from src.retrieval.vector_store import load_vector_store, search_with_scores
from evaluation.llm_judge import load_golden_qa


class RetrievalResult(BaseModel):
    """Retrieval outcome for a single golden question."""
    qa_id: str
    question: str
    expected_sources: list[str]
    retrieved_sources: list[str]
    hit: bool
    reciprocal_rank: float
    top_score: float


def evaluate_retrieval(
    qa_pairs: list[dict[str, Any]],
    vectorstore: Chroma,
    k: int = 3,
    filter: dict | None = None,
) -> list[RetrievalResult]:
    """
    Score retrieval for each QA pair that declares expected source documents.

    Args:
        qa_pairs: Golden QA dicts with 'id', 'question', 'source_documents'.
        vectorstore: Loaded Chroma instance.
        k: How many chunks to retrieve per question.
        filter: Metadata filter (defaults to company_kb).

    Returns:
        One RetrievalResult per QA pair. Pairs with no expected sources are
        included with hit=False but should be excluded from summary stats
        (see summarize_retrieval).
    """
    if filter is None:
        filter = {"source_type": "company_kb"}

    results: list[RetrievalResult] = []
    for p in qa_pairs:
        expected = set(p.get("source_documents") or [])
        scored = search_with_scores(vectorstore, p["question"], k=k, filter=filter)
        retrieved = [doc.metadata.get("source", "") for doc, _ in scored]
        top_score = scored[0][1] if scored else 0.0

        reciprocal_rank = 0.0
        hit = False
        for rank, source in enumerate(retrieved, start=1):
            if source in expected:
                reciprocal_rank = 1.0 / rank
                hit = True
                break

        results.append(RetrievalResult(
            qa_id=p["id"],
            question=p["question"],
            expected_sources=sorted(expected),
            retrieved_sources=retrieved,
            hit=hit,
            reciprocal_rank=reciprocal_rank,
            top_score=round(float(top_score), 3),
        ))
    return results


def summarize_retrieval(results: list[RetrievalResult]) -> dict[str, float]:
    """Aggregate hit@k and MRR over pairs that declared expected sources."""
    scored = [r for r in results if r.expected_sources]
    n = len(scored)
    if n == 0:
        return {"n": 0, "hit_rate": 0.0, "mrr": 0.0}
    return {
        "n": n,
        "hit_rate": round(sum(r.hit for r in scored) / n, 3),
        "mrr": round(sum(r.reciprocal_rank for r in scored) / n, 3),
    }


def print_retrieval_report(results: list[RetrievalResult], k: int) -> None:
    """Print a per-question table plus aggregate hit@k and MRR."""
    print("\n" + "=" * 72)
    print(f"RETRIEVAL EVALUATION  (k={k})")
    print("=" * 72)
    print(f"{'id':<8}{'hit':<5}{'RR':<6}{'top':<7}expected -> top retrieved")
    print("-" * 72)
    for r in results:
        if not r.expected_sources:
            continue
        mark = "yes" if r.hit else "NO"
        top = r.retrieved_sources[0][:32] if r.retrieved_sources else "(none)"
        exp = r.expected_sources[0][:28]
        print(f"{r.qa_id:<8}{mark:<5}{r.reciprocal_rank:<6.2f}{r.top_score:<7.3f}{exp} -> {top}")

    summary = summarize_retrieval(results)
    print("-" * 72)
    print(f"Questions scored: {summary['n']}   "
          f"hit@{k}: {summary['hit_rate']:.1%}   "
          f"MRR: {summary['mrr']:.3f}")
    print("=" * 72)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate retrieval quality on the golden QA set.")
    parser.add_argument("--k", type=int, default=3, help="Chunks to retrieve per question (default: 3)")
    args = parser.parse_args()

    qa_pairs = load_golden_qa()
    vectorstore = load_vector_store()
    results = evaluate_retrieval(qa_pairs, vectorstore, k=args.k)
    print_retrieval_report(results, k=args.k)


if __name__ == "__main__":
    main()
