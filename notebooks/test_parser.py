"""Test the parser on the same PDF from the smoke test."""
from src.ingestion.parser import parse_file

PDF_PATH = "data/company_kb/test.pdf"

docs = parse_file(PDF_PATH, source_type="company_kb")

print(f"Parsed {len(docs)} document(s)")
print(f"\nFirst document metadata:")
for key, value in docs[0].metadata.items():
    print(f"  {key}: {value}")
print(f"\nFirst document content preview:")
print(docs[0].page_content[:300])
print("...")