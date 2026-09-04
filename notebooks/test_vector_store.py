"""Test the vector store module end-to-end."""
from src.ingestion.parser import parse_file
from src.ingestion.chunker import chunk_documents
from src.retrieval.vector_store import index_chunks, load_vector_store, search

PDF_PATH = "data/company_kb/test.pdf"

# Build the index
print("Step 1: Parse + chunk + index...")
docs = parse_file(PDF_PATH, source_type="company_kb")
chunks = chunk_documents(docs)
vectorstore = index_chunks(chunks)
print(f"  Indexed {len(chunks)} chunks\n")

# Search without filter
print("Step 2: Search (no filter)")
results = search(vectorstore, "What is Munther's experience?", k=2)
for i, r in enumerate(results):
    print(f"  Result {i+1}: source={r.metadata.get('source')}, chunk_index={r.metadata.get('chunk_index')}")
    print(f"           preview: {r.page_content[:100]}...")
print()

# Search with filter — only company_kb
print("Step 3: Search (filter source_type=company_kb)")
results = search(vectorstore, "What is Munther's experience?", k=2, filter={"source_type": "company_kb"})
print(f"  Got {len(results)} results (filter applied)")
print()

# Search with filter — incoming_rfp (should return nothing — we only indexed company_kb)
print("Step 4: Search (filter source_type=incoming_rfp — should return 0)")
results = search(vectorstore, "What is Munther's experience?", k=2, filter={"source_type": "incoming_rfp"})
print(f"  Got {len(results)} results (correctly empty)")
print()

# Now test load_vector_store — reopen the existing index without re-embedding
print("Step 5: Load existing index (no re-embedding)")
vectorstore_loaded = load_vector_store()
results = search(vectorstore_loaded, "What is Munther's experience?", k=1)
print(f"  Loaded and searched. Top result chunk_index={results[0].metadata.get('chunk_index')}")