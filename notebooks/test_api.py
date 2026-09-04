"""
End-to-end API smoke test.

Requires the API to be running:
    uvicorn src.api.main:app --reload

Tests:
  1. GET  /health          — confirms server is up and KB is loaded
  2. POST /query           — basic Q&A against the company KB
  3. POST /query verify=true — same Q&A with verification enabled
  4. POST /analyze-rfp     — upload an RFP and check the analysis report structure

Usage:
    python notebooks/test_api.py
"""
import sys
from pathlib import Path

try:
    import httpx
except ImportError:
    print("httpx not installed. Run: python -m pip install httpx")
    sys.exit(1)

BASE_URL = "http://127.0.0.1:8000"
RFP_DIR = Path("data/incoming_rfps")


def find_rfp() -> Path | None:
    for ext in (".pdf", ".docx", ".pptx"):
        matches = list(RFP_DIR.glob(f"*{ext}"))
        if matches:
            return matches[0]
    return None


def main() -> None:
    client = httpx.Client(base_url=BASE_URL, timeout=120.0)

    # ------------------------------------------------------------------
    # 1. Health check
    # ------------------------------------------------------------------
    print("Test 1: GET /health")
    resp = client.get("/health")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    data = resp.json()
    assert data["status"] == "ok", f"Status not ok: {data}"
    assert data["vectorstore_loaded"], "Vector store not loaded — run index_corpus.py"
    print(f"  PASSED — {data}\n")

    # ------------------------------------------------------------------
    # 2. Basic query
    # ------------------------------------------------------------------
    print("Test 2: POST /query (basic)")
    resp = client.post("/query", json={
        "question": "What AI services did IBTech deliver?",
        "k": 3,
    })
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    answer = resp.json()
    assert "answer" in answer
    assert "refused" in answer
    assert "sources" in answer
    assert answer.get("verification") is None
    print(f"  refused={answer['refused']}")
    print(f"  sources={len(answer['sources'])} chunk(s)")
    print(f"  answer preview: {answer['answer'][:150]}...")
    print("  PASSED\n")

    # ------------------------------------------------------------------
    # 3. Query with verification
    # ------------------------------------------------------------------
    print("Test 3: POST /query (verify=true)")
    resp = client.post("/query", json={
        "question": "What technology stack was used in the Jouf University project?",
        "k": 3,
        "verify": True,
    })
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    answer = resp.json()
    if not answer["refused"]:
        assert answer.get("verification") is not None, "verification block missing"
        v = answer["verification"]
        assert "faithful" in v
        assert "complete" in v
        print(f"  faithful={v['faithful']}  complete={v['complete']}")
        print(f"  missed_points={v.get('missed_points', [])}")
        print("  PASSED\n")
    else:
        print("  LLM refused (corpus may be too small) — skipping verification check\n")

    # ------------------------------------------------------------------
    # 4. /analyze-rfp with file upload
    # ------------------------------------------------------------------
    rfp_path = find_rfp()
    if not rfp_path:
        print("Test 4: /analyze-rfp — SKIPPED (no RFP file found in data/incoming_rfps/)")
        return

    print(f"Test 4: POST /analyze-rfp (uploading {rfp_path.name})")
    with open(rfp_path, "rb") as f:
        resp = client.post(
            "/analyze-rfp",
            files={"file": (rfp_path.name, f, "application/octet-stream")},
        )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    report = resp.json()
    assert "requirements" in report
    assert "clarifying_questions" in report
    assert "coverage_summary" in report
    s = report["coverage_summary"]
    total = s["fully_covered"] + s["partially_covered"] + s["not_covered"]
    print(f"  Requirements assessed: {total}")
    print(f"  Coverage: ✓{s['fully_covered']}  ~{s['partially_covered']}  ✗{s['not_covered']}")
    print(f"  Clarifying questions: {len(report['clarifying_questions'])}")
    print("  PASSED\n")

    print("All API tests passed.")


if __name__ == "__main__":
    main()
