"""
Benchmark the RETRIEVE step (basic vs. cross-encoder reranking).

For each golden question that declares expected source_documents, retrieve k
chunks two ways — plain vector search and over-fetch + rerank — and score:
  - hit@k            : an expected source appears in the top-k
  - reciprocal rank  : 1/rank of the first expected source (→ MRR)
  - precision@k      : fraction of top-k chunks from an expected source
No generation, so this isolates retrieval quality. Builds a temp index from the
company KB (production chunk settings). Writes benchmarks/results/retrieval_*.csv.

Run:  python benchmarks/benchmark_retrieval.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchmarks import _utils as u

K = 3
SETUPS = {
    "basic": u.retrieve_basic,
    "reranked": u.retrieve_reranked,
}


def main() -> None:
    qa_pairs = [p for p in u.load_golden() if p.get("source_documents")]
    if not qa_pairs:
        print("No golden QA pairs with source_documents. Nothing to score.")
        return
    print(f"Scoring retrieval on {len(qa_pairs)} golden question(s) at k={K}.\n")

    vs, tmp_dir = u.build_temp_index(chunk_size=500, overlap=50)
    rows = []
    try:
        for setup, retrieve in SETUPS.items():
            for p in qa_pairs:
                scored = retrieve(vs, p["question"], k=K)
                sources = u.sources_of(scored)
                expected = set(p["source_documents"])
                rr, hit = 0.0, False
                for rank, src in enumerate(sources, start=1):
                    if src in expected:
                        rr, hit = 1.0 / rank, True
                        break
                rows.append({
                    "setup": setup,
                    "qa_id": p["id"],
                    "hit": int(hit),
                    "reciprocal_rank": round(rr, 3),
                    "precision_at_k": round(u.precision_at_k(sources, expected, K), 3),
                    "top_score": round(scored[0][1], 3) if scored else 0.0,
                })
    finally:
        u.cleanup(tmp_dir)

    # Aggregate per setup.
    print(f"{'setup':<12}{'hit@k':<8}{'MRR':<8}{'precision@k':<12}")
    print("-" * 40)
    summary_rows = []
    for setup in SETUPS:
        sub = [r for r in rows if r["setup"] == setup]
        n = len(sub)
        agg = {
            "setup": setup,
            "questions": n,
            "hit_rate": round(sum(r["hit"] for r in sub) / n, 3),
            "mrr": round(sum(r["reciprocal_rank"] for r in sub) / n, 3),
            "precision_at_k": round(sum(r["precision_at_k"] for r in sub) / n, 3),
        }
        summary_rows.append(agg)
        print(f"{setup:<12}{agg['hit_rate']:<8}{agg['mrr']:<8}{agg['precision_at_k']:<12}")

    detail_path = u.write_csv(rows, "retrieval_detail")
    summary_path = u.write_csv(summary_rows, "retrieval_summary")
    print(f"\nSaved: {summary_path}\n       {detail_path}")


if __name__ == "__main__":
    main()
