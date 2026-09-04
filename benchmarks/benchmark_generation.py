"""
Benchmark the GENERATE step.

For three setups — LLM only, basic RAG, RAG + reranking — answer every golden
question and score the answer with the LLM judge (faithfulness + relevance, 0-10
from src.generation.judge). Writes benchmarks/results/generation_*.csv.

Needs a configured LLM provider (Admin/.env). Builds a temp index from the KB.

Run:  python benchmarks/benchmark_generation.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchmarks import _utils as u
from src import config
from src.generation.generator import generate_answer
from src.generation.judge import evaluate_answer

_NO_RAG_PROMPT = (
    "Answer the following question based on your general knowledge. "
    "Be concise and professional.\n\nQuestion: {question}\n\nAnswer:"
)


def _answer_llm_only(question: str) -> tuple[str, list[str]]:
    llm = config.get_llm()
    resp = llm.invoke(config.date_prefix() + _NO_RAG_PROMPT.format(question=question))
    return resp.content, []


def _answer_rag(question: str, retrieve) -> tuple[str, list[str]]:
    scored = retrieve(_VS, question, k=3)
    docs = [doc for doc, _ in scored]
    if not docs:
        return "No relevant documents found.", []
    answer = generate_answer(question, docs)
    return answer.answer, [d.page_content for d in docs]


SETUPS = {
    "llm_only": lambda q: _answer_llm_only(q),
    "basic_rag": lambda q: _answer_rag(q, u.retrieve_basic),
    "rag_reranked": lambda q: _answer_rag(q, u.retrieve_reranked),
}

_VS = None


def main() -> None:
    global _VS
    qa_pairs = u.load_golden()
    if not qa_pairs:
        print("No golden QA pairs. Run notebooks/generate_golden_qa.py first.")
        return
    print(f"Scoring generation on {len(qa_pairs)} golden question(s).\n")

    _VS, tmp_dir = u.build_temp_index(chunk_size=500, overlap=50)
    rows = []
    try:
        for setup, answer_fn in SETUPS.items():
            print(f"Setup: {setup} …")
            for p in qa_pairs:
                answer, contexts = answer_fn(p["question"])
                ev = evaluate_answer(p["question"], answer, contexts)
                rows.append({
                    "setup": setup,
                    "qa_id": p["id"],
                    "faithfulness": ev.scores.faithfulness,
                    "relevance": ev.scores.relevance,
                })
    finally:
        u.cleanup(tmp_dir)

    print(f"\n{'setup':<14}{'faithfulness':<14}{'relevance':<12}")
    print("-" * 40)
    summary_rows = []
    for setup in SETUPS:
        sub = [r for r in rows if r["setup"] == setup]
        n = len(sub)
        agg = {
            "setup": setup,
            "avg_faithfulness": round(sum(r["faithfulness"] for r in sub) / n, 2),
            "avg_relevance": round(sum(r["relevance"] for r in sub) / n, 2),
        }
        summary_rows.append(agg)
        print(f"{setup:<14}{agg['avg_faithfulness']:<14}{agg['avg_relevance']:<12}")

    detail_path = u.write_csv(rows, "generation_detail")
    summary_path = u.write_csv(summary_rows, "generation_summary")
    print(f"\nSaved: {summary_path}\n       {detail_path}")


if __name__ == "__main__":
    main()
