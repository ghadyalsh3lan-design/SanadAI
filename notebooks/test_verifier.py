"""
Smoke test for the verifier module.

Tests:
  1. A faithful and complete answer — should pass both checks.
  2. An answer with a fabricated claim — should flag unfaithful.
  3. An answer that misses key points — should flag incomplete.

Usage:
    python notebooks/test_verifier.py
"""
from langchain_core.documents import Document

from src.generation.verifier import verify_answer

FAKE_CHUNK = Document(
    page_content=(
        "IBTech delivered a full AI transformation roadmap for Jouf University, "
        "including a custom NLP pipeline for Arabic text, a data lake on AWS, "
        "and a 6-month training program for 120 university staff. "
        "The project was completed in Q3 2024 with a 98% satisfaction score."
    ),
    metadata={"source": "Jouf University Proposal by IBTech v2.0.docx", "chunk_index": 0},
)

QUESTION = "What did IBTech deliver for Jouf University?"

print("=" * 60)
print("Test 1: Faithful and complete answer")
print("=" * 60)
good_answer = (
    "IBTech delivered an AI transformation roadmap, a custom NLP pipeline for Arabic text, "
    "a data lake on AWS, and a 6-month training program for 120 university staff."
)
result = verify_answer(QUESTION, good_answer, [FAKE_CHUNK])
print(f"Faithful:  {result.faithful}")
print(f"Complete:  {result.complete}")
print(f"Missed:    {result.missed_points}")
print(f"Flagged:   {result.flagged_claims}")
assert result.faithful, "Expected faithful=True for grounded answer"
print("PASSED\n")

print("=" * 60)
print("Test 2: Answer with a fabricated claim")
print("=" * 60)
hallucinated_answer = (
    "IBTech delivered an NLP pipeline, a data lake, and also built a mobile app "
    "for 500 students — which won a national innovation award."
)
result2 = verify_answer(QUESTION, hallucinated_answer, [FAKE_CHUNK])
print(f"Faithful:  {result2.faithful}")
print(f"Complete:  {result2.complete}")
print(f"Flagged:   {result2.flagged_claims}")
assert not result2.faithful, "Expected faithful=False for hallucinated answer"
print("PASSED\n")

print("=" * 60)
print("Test 3: Answer that misses key points")
print("=" * 60)
incomplete_answer = "IBTech delivered a data lake for Jouf University."
result3 = verify_answer(QUESTION, incomplete_answer, [FAKE_CHUNK])
print(f"Faithful:  {result3.faithful}")
print(f"Complete:  {result3.complete}")
print(f"Missed:    {result3.missed_points}")
assert not result3.complete, "Expected complete=False for incomplete answer"
print("PASSED\n")

print("All verifier tests passed.")
