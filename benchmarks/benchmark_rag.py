"""
End-to-end RAG benchmark — the rubric table.

Compares four setups over the golden QA set and reports Faithfulness, Relevance
(LLM judge, 0-10) and Retrieval Precision (precision@k vs. expected sources):

    Setup            Faithfulness  Relevance  Retrieval Precision  Notes
    LLM Only         …             …          N/A                  Hallucination risk
    Basic RAG        …             …          …                    Baseline
    Optimized RAG    …             …          …                    Improved
    RAG + reranking  …             …          …                    Advanced

Needs a configured LLM provider (Admin/.env) and documents in data/company_kb.
Writes benchmarks/results/rag_*.csv.

Run:  python benchmarks/benchmark_rag.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchmarks import _utils as u
from src import config
from src.generation.generator import generate_answer
from src.generation.judge import evaluate_answer

K = 3
_NO_RAG_PROMPT = (
    "Answer the following question based on your general knowledge. "
    "Be concise and professional.\n\nQuestion: {question}\n\nAnswer:"
)


def _score(question: str, answer: str, contexts: list[str]):
    ev = evaluate_answer(question, answer, contexts)
    return ev.scores.faithfulness, ev.scores.relevance


def main() -> None:
    qa_pairs = u.load_golden()
    if not qa_pairs:
        print("No golden QA pairs. Run notebooks/generate_golden_qa.py first.")
        return
    print(f"Benchmarking {len(qa_pairs)} golden question(s) at k={K}.\n")

    basic_vs, basic_dir = u.build_temp_index(chunk_size=500, overlap=50)
    opt_vs, opt_dir = u.build_temp_index(chunk_size=900, overlap=100)

    # (label, note, retrieve_fn_or_None, vectorstore_or_None)
    setups = [
        ("LLM Only", "Hallucination risk", None, None),
        ("Basic RAG", "Baseline", u.retrieve_basic, basic_vs),
        ("Optimized RAG", "Improved", u.retrieve_basic, opt_vs),
        ("RAG + reranking", "Advanced", u.retrieve_reranked, opt_vs),
    ]

    rows = []
    try:
        for label, note, retrieve, vs in setups:
            print(f"Setup: {label} …")
            faiths, rels, precs = [], [], []
            for p in qa_pairs:
                if retrieve is None:  # LLM only
                    llm = config.get_llm()
                    answer = llm.invoke(
                        config.date_prefix() + _NO_RAG_PROMPT.format(question=p["question"])
                    ).content
                    contexts = []
                else:
                    scored = retrieve(vs, p["question"], k=K)
                    docs = [doc for doc, _ in scored]
                    contexts = [d.page_content for d in docs]
                    answer = generate_answer(p["question"], docs).answer if docs else "No relevant documents found."
                    if p.get("source_documents"):
                        precs.append(u.precision_at_k(u.sources_of(scored), p["source_documents"], K))
                f, r = _score(p["question"], answer, contexts)
                faiths.append(f)
                rels.append(r)

            n = len(qa_pairs)
            rows.append({
                "setup": label,
                "faithfulness": round(sum(faiths) / n, 2),
                "relevance": round(sum(rels) / n, 2),
                "retrieval_precision": "N/A" if not precs else round(sum(precs) / len(precs), 3),
                "notes": note,
            })
    finally:
        u.cleanup(basic_dir)
        u.cleanup(opt_dir)

    # Rubric table
    print(f"\n{'Setup':<18}{'Faithfulness':<14}{'Relevance':<12}{'Retr.Precision':<16}{'Notes'}")
    print("-" * 76)
    for r in rows:
        prec = r["retrieval_precision"]
        prec_str = prec if prec == "N/A" else f"{prec:.3f}"
        print(f"{r['setup']:<18}{r['faithfulness']:<14}{r['relevance']:<12}{prec_str:<16}{r['notes']}")

    path = u.write_csv(rows, "rag")
    print(f"\nSaved: {path}")


if __name__ == "__main__":
    main()
