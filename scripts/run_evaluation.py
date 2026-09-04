"""
Evaluation runner for the RFP Intelligence System.

Compares three benchmark configurations against the golden QA set:

  A — No-RAG:       LLM answers the question with no retrieved context
  B — Basic RAG:    chunk_size=500, overlap=50 (production defaults)
  C — Optimized RAG: chunk_size=1000, overlap=100 (wider context windows)

Results are scored by the LLM judge (faithfulness + completeness) and printed
as a comparison table. Optional: also runs RAGAS metrics if available.

Usage:
    python scripts/run_evaluation.py
    python scripts/run_evaluation.py --benchmark B   # run only one benchmark
    python scripts/run_evaluation.py --skip-ragas    # skip RAGAS (faster)
"""
import argparse
import json
import sys
import tempfile
import shutil
from pathlib import Path

# Make the repo root importable so `evaluation` resolves when this file is run
# directly as a script (only `src` is on the path via `pip install -e .`).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langchain_core.documents import Document

from src import config
from src.retrieval.vector_store import (
    load_vector_store,
    index_chunks,
    search,
    DEFAULT_PERSIST_DIR,
)
from src.ingestion.parser import parse_file
from src.ingestion.chunker import chunk_documents
from evaluation.llm_judge import load_golden_qa, batch_judge, print_summary, EvaluationResult
from evaluation.retrieval_eval import evaluate_retrieval, print_retrieval_report

COMPANY_KB_DIR = Path("data/company_kb")
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".md", ".txt"}

NO_RAG_PROMPT = """Answer the following question based on your general knowledge.
Be concise and professional.

Question: {question}

Answer:"""


def _run_no_rag(questions: list[str], model: str | None = None) -> list[str]:
    """Benchmark A: answer with no retrieved context."""
    llm = config.get_llm(model)
    responses = []
    for q in questions:
        resp = llm.invoke(config.date_prefix() + NO_RAG_PROMPT.format(question=q))
        responses.append(resp.content)
    return responses


def _run_rag(
    questions: list[str],
    vectorstore,
    k: int = 3,
    model: str | None = None,
) -> tuple[list[str], list[list[str]]]:
    """Benchmark B/C: answer using retrieved context from the vector store.

    Returns both the answers and the retrieved contexts (one list of chunk
    texts per question) so RAGAS can score faithfulness against the actual
    context the answer was grounded in.
    """
    from src.generation.generator import generate_answer
    responses: list[str] = []
    contexts: list[list[str]] = []
    for q in questions:
        chunks = search(vectorstore, q, k=k, filter={"source_type": "company_kb"})
        contexts.append([c.page_content for c in chunks])
        if not chunks:
            responses.append("No relevant documents found.")
            continue
        answer = generate_answer(q, chunks, model=model)
        responses.append(answer.answer)
    return responses, contexts


def _build_optimized_index(chunk_size: int = 1000, overlap: int = 100) -> object:
    """Build a temporary Chroma index with different chunker settings for benchmark C."""
    files = [
        f for f in COMPANY_KB_DIR.iterdir()
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    all_chunks = []
    for f in files:
        docs = parse_file(f, source_type="company_kb")
        all_chunks.extend(chunk_documents(docs, chunk_size=chunk_size, chunk_overlap=overlap))

    tmp_dir = tempfile.mkdtemp(prefix="rfp_eval_c_")
    return index_chunks(all_chunks, persist_dir=tmp_dir), tmp_dir


def run_evaluation(benchmarks: list[str], skip_ragas: bool = False) -> None:
    print("\nRFP Intelligence — Evaluation Run")
    print("=" * 60)

    qa_pairs = load_golden_qa()
    if not qa_pairs:
        print(
            "ERROR: golden_qa.json has no completed entries.\n"
            "Run `python notebooks/generate_golden_qa.py` then fill in the ground truths."
        )
        sys.exit(1)

    questions = [p["question"] for p in qa_pairs]
    print(f"Loaded {len(qa_pairs)} QA pairs.\n")

    all_results: list[EvaluationResult] = []

    # -----------------------------------------------------------------------
    # Retrieval quality (no LLM) — does the retriever find the right document?
    # Cheap, deterministic, and independent of generation. Runs whenever the
    # production index exists, regardless of which generation benchmarks run.
    # -----------------------------------------------------------------------
    if Path(DEFAULT_PERSIST_DIR).exists():
        print("Evaluating retrieval quality on the golden set...")
        retrieval_results = evaluate_retrieval(qa_pairs, load_vector_store(), k=3)
        print_retrieval_report(retrieval_results, k=3)
    else:
        print(f"(Skipping retrieval eval — no index at {DEFAULT_PERSIST_DIR}.)")

    # -----------------------------------------------------------------------
    # Benchmark A — No RAG
    # -----------------------------------------------------------------------
    if "A" in benchmarks:
        print("Running Benchmark A (no-RAG)...")
        responses_a = _run_no_rag(questions)
        results_a = batch_judge(qa_pairs, responses_a, benchmark_name="A_no_rag")
        all_results.extend(results_a)

    # -----------------------------------------------------------------------
    # Benchmark B — Basic RAG (production settings)
    # -----------------------------------------------------------------------
    if "B" in benchmarks:
        print("\nRunning Benchmark B (basic RAG, chunk_size=500)...")
        if not Path(DEFAULT_PERSIST_DIR).exists():
            print(f"ERROR: No vector store at {DEFAULT_PERSIST_DIR}. Run index_corpus.py first.")
            sys.exit(1)
        vs_b = load_vector_store()
        responses_b, contexts_b = _run_rag(questions, vs_b)
        results_b = batch_judge(qa_pairs, responses_b, benchmark_name="B_basic_rag")
        all_results.extend(results_b)

    # -----------------------------------------------------------------------
    # Benchmark C — Optimized RAG (larger chunks)
    # -----------------------------------------------------------------------
    tmp_dir_c = None
    if "C" in benchmarks:
        print("\nRunning Benchmark C (optimized RAG, chunk_size=1000)...")
        vs_c, tmp_dir_c = _build_optimized_index()
        responses_c, _contexts_c = _run_rag(questions, vs_c, k=3)
        results_c = batch_judge(qa_pairs, responses_c, benchmark_name="C_optimized_rag")
        all_results.extend(results_c)
        shutil.rmtree(tmp_dir_c, ignore_errors=True)

    # -----------------------------------------------------------------------
    # Optional RAGAS scoring
    # -----------------------------------------------------------------------
    if not skip_ragas and "B" in benchmarks:
        try:
            _run_ragas(qa_pairs, responses_b, contexts_b)  # type: ignore[possibly-undefined]
        except ImportError:
            print(
                "\n[RAGAS] Skipped — ragas is not installed. "
                "Install it with `pip install ragas` to enable these metrics."
            )
        except Exception as e:
            print(f"\n[RAGAS] Skipped — {e}")

    # -----------------------------------------------------------------------
    # Summary table
    # -----------------------------------------------------------------------
    if all_results:
        print_summary(all_results)

        # Save results to file
        results_dir = Path("evaluation/results")
        results_dir.mkdir(exist_ok=True)
        from datetime import datetime
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = results_dir / f"eval_{ts}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(
                [r.model_dump() for r in all_results],
                f,
                indent=2,
                default=str,
            )
        print(f"\nResults saved to {out_path}")


def _run_ragas(
    qa_pairs: list[dict],
    responses: list[str],
    contexts: list[list[str]],
) -> None:
    """Run RAGAS faithfulness + answer relevancy on the basic RAG responses.

    RAGAS defaults to OpenAI; we point it at the same Groq LLM and local
    HuggingFace embeddings the system already uses, and feed it the *real*
    retrieved contexts (without which faithfulness is meaningless).

    Raises:
        ImportError: If ragas is not installed (handled by the caller).
    """
    from ragas import EvaluationDataset, evaluate
    from ragas.llms import LangchainLLMWrapper
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.metrics import Faithfulness, ResponseRelevancy

    from src.retrieval.vector_store import _get_embeddings

    print("\n[RAGAS] Running faithfulness + answer relevancy (local embeddings)...")

    dataset = EvaluationDataset.from_list([
        {
            "user_input": p["question"],
            "response": resp,
            "retrieved_contexts": ctx or [""],
            "reference": p["ground_truth"],
        }
        for p, resp, ctx in zip(qa_pairs, responses, contexts)
    ])

    llm = LangchainLLMWrapper(config.get_llm())
    embeddings = LangchainEmbeddingsWrapper(_get_embeddings())

    result = evaluate(
        dataset=dataset,
        metrics=[Faithfulness(), ResponseRelevancy()],
        llm=llm,
        embeddings=embeddings,
    )
    print(f"[RAGAS] {result}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run RFP Intelligence evaluation benchmarks.")
    parser.add_argument(
        "--benchmark",
        choices=["A", "B", "C", "AB", "ABC"],
        default="ABC",
        help="Which benchmarks to run (default: ABC)",
    )
    parser.add_argument(
        "--skip-ragas",
        action="store_true",
        help="Skip RAGAS metrics (faster, no OpenAI key needed)",
    )
    args = parser.parse_args()
    benchmarks = list(args.benchmark)
    run_evaluation(benchmarks=benchmarks, skip_ragas=args.skip_ragas)
