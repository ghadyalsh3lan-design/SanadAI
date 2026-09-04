"""Test the generation module."""
from src.ingestion.parser import parse_file
from src.ingestion.chunker import chunk_documents
from src.retrieval.vector_store import index_chunks, search
from src.generation.generator import generate_answer
from dotenv import load_dotenv

load_dotenv()

PDF_PATH = "data/company_kb/test.pdf"

# Build the pipeline up to retrieval
docs = parse_file(PDF_PATH, source_type="company_kb")
chunks = chunk_documents(docs)
vectorstore = index_chunks(chunks)

# Test 1 — grounded question (should answer)
print("=" * 60)
print("Test 1: Grounded question (should answer)")
print("=" * 60)
question_1 = "What is Munther's experience with AI engineering?"
retrieved = search(vectorstore, question_1, k=3, filter={"source_type": "company_kb"})
answer = generate_answer(question_1, retrieved)

print(f"\nQuestion: {question_1}")
print(f"Refused: {answer.refused}")
print(f"\nAnswer: {answer.answer}")
print(f"\nSources ({len(answer.sources)}):")
for s in answer.sources:
    print(f"  - {s.source}, chunk {s.chunk_index}, page {s.page}")
    print(f"    preview: {s.preview[:80]}...")

# Test 2 — ungrounded question (should refuse)
print("\n" + "=" * 60)
print("Test 2: Ungrounded question (should refuse)")
print("=" * 60)
question_2 = "What is the capital of France?"
retrieved = search(vectorstore, question_2, k=3, filter={"source_type": "company_kb"})
answer = generate_answer(question_2, retrieved)

print(f"\nQuestion: {question_2}")
print(f"Refused: {answer.refused}")
print(f"\nAnswer: {answer.answer}")
print(f"Sources attached: {len(answer.sources)}")