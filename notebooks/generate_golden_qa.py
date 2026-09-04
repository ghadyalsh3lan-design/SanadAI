"""
Generate golden QA pairs from the indexed company knowledge base.

This script queries the KB with each question from golden_qa.json, gets the
RAG system's best answer, and prints it alongside the question. Review and edit
the output, then paste the ground truths back into evaluation/golden_qa.json.

Usage:
    python notebooks/generate_golden_qa.py
"""
import json
from pathlib import Path

from src.retrieval.vector_store import load_vector_store, search
from src.generation.generator import generate_answer

GOLDEN_QA_PATH = Path("evaluation/golden_qa.json")


def main() -> None:
    print("Loading vector store...")
    vs = load_vector_store()

    with open(GOLDEN_QA_PATH, encoding="utf-8") as f:
        qa_pairs = json.load(f)

    print(f"Generating candidate answers for {len(qa_pairs)} questions.\n")
    print("=" * 70)
    print("Review each answer. If it's correct and grounded, copy it into")
    print("golden_qa.json as the 'ground_truth' for that question.")
    print("=" * 70 + "\n")

    results = []
    for pair in qa_pairs:
        q = pair["question"]
        chunks = search(vs, q, k=4, filter={"source_type": "company_kb"})

        if not chunks:
            candidate = "No relevant documents found in the knowledge base."
        else:
            answer = generate_answer(q, chunks)
            candidate = answer.answer if not answer.refused else "(LLM refused — insufficient context)"

        results.append({**pair, "candidate_answer": candidate})

        print(f"[{pair['id']}] {pair['category']}")
        print(f"Q: {q}")
        print(f"A: {candidate[:300]}{'...' if len(candidate) > 300 else ''}")
        print()

    # Save to a draft file for easy copy-paste
    draft_path = Path("evaluation/golden_qa_draft.json")
    with open(draft_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\nDraft saved to {draft_path}")
    print("Edit the 'candidate_answer' fields, rename them to 'ground_truth', "
          "and copy back into evaluation/golden_qa.json.")


if __name__ == "__main__":
    main()
