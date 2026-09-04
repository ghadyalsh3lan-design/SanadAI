"""Test the chunker on the parsed test PDF."""
from src.ingestion.parser import parse_file
from src.ingestion.chunker import chunk_documents

PDF_PATH = "data/company_kb/test.pdf"

# Parse first
docs = parse_file(PDF_PATH, source_type="company_kb")
print(f"Parser produced: {len(docs)} document(s)")

# Then chunk
chunks = chunk_documents(docs)
print(f"Chunker produced: {len(chunks)} chunks\n")

# Inspect the first chunk
print("First chunk metadata:")
for key, value in chunks[0].metadata.items():
    print(f"  {key}: {value}")

print(f"\nFirst chunk content ({len(chunks[0].page_content)} chars):")
print(chunks[0].page_content)
print()

# Inspect the second chunk to see the overlap
if len(chunks) > 1:
    print(f"Second chunk content ({len(chunks[1].page_content)} chars):")
    print(chunks[1].page_content)
    print()

# Quick stats
chunk_lengths = [len(c.page_content) for c in chunks]
print(f"Chunk size stats: min={min(chunk_lengths)}, max={max(chunk_lengths)}, avg={sum(chunk_lengths)//len(chunk_lengths)}")