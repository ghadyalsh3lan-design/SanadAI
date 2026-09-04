"""
Benchmark the CHUNK step.

For several chunk-size / overlap configurations, parse the whole company KB once
per config and measure how many chunks result and their size distribution. No LLM
needed — fast and deterministic. Writes benchmarks/results/chunking_*.csv.

Run:  python benchmarks/benchmark_chunking.py
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchmarks import _utils as u
from src.ingestion.parser import parse_file
from src.ingestion.chunker import chunk_documents

CONFIGS = [(500, 50), (900, 150), (1000, 100)]


def main() -> None:
    files = u.kb_files()
    if not files:
        print(f"No documents in {u.COMPANY_KB_DIR}. Add files to benchmark chunking.")
        return

    # Parse once; reuse the parsed documents across every chunk config.
    parsed = []
    for f in files:
        parsed.extend(parse_file(f, source_type="company_kb"))
    print(f"Parsed {len(parsed)} document object(s) from {len(files)} file(s).\n")

    rows = []
    for size, overlap in CONFIGS:
        start = time.perf_counter()
        chunks = chunk_documents(parsed, chunk_size=size, chunk_overlap=overlap)
        seconds = round(time.perf_counter() - start, 3)
        lengths = [len(c.page_content) for c in chunks] or [0]
        rows.append({
            "chunk_size": size,
            "overlap": overlap,
            "num_chunks": len(chunks),
            "avg_chars": round(sum(lengths) / len(lengths)),
            "min_chars": min(lengths),
            "max_chars": max(lengths),
            "seconds": seconds,
        })

    print(f"{'size':<7}{'overlap':<9}{'chunks':<9}{'avg':<7}{'min':<7}{'max':<7}{'sec':<7}")
    print("-" * 52)
    for r in rows:
        print(f"{r['chunk_size']:<7}{r['overlap']:<9}{r['num_chunks']:<9}"
              f"{r['avg_chars']:<7}{r['min_chars']:<7}{r['max_chars']:<7}{r['seconds']:<7}")

    path = u.write_csv(rows, "chunking")
    print(f"\nSaved: {path}")


if __name__ == "__main__":
    main()
