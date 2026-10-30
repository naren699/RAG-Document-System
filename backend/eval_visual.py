"""Evaluate visual retrieval: compare text-only vs text+visual for table/chart queries."""

import csv
import json
import os
import sys
import time
from pathlib import Path

DOCS_DIR = Path(__file__).parent.parent / "docs"
API_BASE = os.getenv("API_BASE", "http://localhost:8000")

VISUAL_QUERIES = [
    {"query_id": "v1", "query": "What data is shown in the table?", "category": "visual"},
    {"query_id": "v2", "query": "Describe the chart on this page.", "category": "visual"},
    {"query_id": "v3", "query": "What are the values in the table?", "category": "visual"},
    {"query_id": "v4", "query": "Summarize the graph.", "category": "visual"},
    {"query_id": "v5", "query": "What trends does the chart show?", "category": "visual"},
]


def run_query(query: str, doc_id: str | None = None) -> dict:
    import urllib.request

    payload = json.dumps({
        "query": query,
        "k": 5,
        "method": "hybrid",
        "doc_id": doc_id,
    }).encode()
    req = urllib.request.Request(
        f"{API_BASE}/api/query",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    start = time.time()
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())
    elapsed = time.time() - start
    data["latency_s"] = round(elapsed, 2)
    return data


def run_comparison(queries: list[dict], doc_id: str | None = None) -> list[dict]:
    results = []
    for q in queries:
        print(f"  Query: {q['query']}")
        try:
            result = run_query(q["query"], doc_id)
            has_visual = any(
                s.get("page_type") in ("visual", "visual_fallback")
                for s in result.get("sources", [])
            )
            results.append({
                "query_id": q["query_id"],
                "query": q["query"],
                "answer_length": len(result.get("answer", "")),
                "sources_count": len(result.get("sources", [])),
                "has_visual_source": has_visual,
                "latency_s": result.get("latency_s", 0),
                "is_not_found": result.get("is_not_found", False),
            })
            print(f"    -> {len(result.get('sources', []))} sources, visual={has_visual}")
        except Exception as e:
            print(f"    -> ERROR: {e}")
            results.append({
                "query_id": q["query_id"],
                "query": q["query"],
                "answer_length": 0,
                "sources_count": 0,
                "has_visual_source": False,
                "latency_s": 0,
                "is_not_found": True,
                "error": str(e),
            })
    return results


def save_results(results: list[dict], filename: str) -> None:
    out = DOCS_DIR / filename
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    fieldnames = ["query_id", "query", "answer_length", "sources_count",
                  "has_visual_source", "latency_s", "is_not_found"]
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)
    print(f"\nResults saved to {out}")


if __name__ == "__main__":
    doc_id = sys.argv[1] if len(sys.argv) > 1 else None

    print("Running visual retrieval evaluation...")
    print(f"  API: {API_BASE}")
    print(f"  doc_id: {doc_id or 'all'}")
    print(f"  Queries: {len(VISUAL_QUERIES)}\n")

    results = run_comparison(VISUAL_QUERIES, doc_id)

    visual_found = sum(1 for r in results if r["has_visual_source"])
    total = len(results)
    print(f"\nVisual sources found: {visual_found}/{total}")
    save_results(results, "visual-eval-results.csv")
