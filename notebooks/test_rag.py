"""
End-to-end RAG smoke test using the real ingestion + retrieval modules.

Generation is still inline — it becomes src.generation in the next step.
"""
from dotenv import load_dotenv

from langchain_groq import ChatGroq

from src.ingestion.parser import parse_file
from src.ingestion.chunker import chunk_documents
from src.retrieval.vector_store import index_chunks, search

load_dotenv()

PDF_PATH = "data/company_kb/test.pdf"
QUESTION = "What is Munther's experience with AI engineering?"

# 1. PARSE
print("Step 1: Parsing the document...")
documents = parse_file(PDF_PATH, source_type="company_kb")
print(f"  Parsed {len(documents)} document object(s)\n")

# 2. CHUNK
print("Step 2: Chunking...")
chunks = chunk_documents(documents)
print(f"  Produced {len(chunks)} chunks\n")

# 3. INDEX
print("Step 3: Indexing in vector store...")
vectorstore = index_chunks(chunks)
print(f"  Indexed {len(chunks)} chunks\n")

# 4. RETRIEVE
print(f"Step 4: Searching for: '{QUESTION}'")
results = search(vectorstore, QUESTION, k=3, filter={"source_type": "company_kb"})
print(f"  Retrieved {len(results)} chunks")
print(f"  Top result: source={results[0].metadata.get('source')}, chunk_index={results[0].metadata.get('chunk_index')}\n")

# 5. GENERATE — still inline, becomes src.generation next
print("Step 5: Asking the LLM...")
context = "\n\n".join([r.page_content for r in results])
prompt = f"""Use ONLY the following context to answer the question. If the context doesn't contain the answer, say "I don't know."

Context:
{context}

Question: {QUESTION}

Answer:"""

llm = ChatGroq(model="llama-3.3-70b-versatile")
response = llm.invoke(prompt)
print(f"\n  ANSWER: {response.content}")