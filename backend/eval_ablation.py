"""
Phase 4.4 — Ablation Studies

Compares retrieval methods: hybrid (dense+BM25) vs dense-only vs BM25-only.
Uses a subset of queries to conserve API quota.

Usage:
    python -I eval_ablation.py
    python -I eval_ablation.py --delay 10
    python -I eval_ablation.py --dry-run
"""

import argparse
import csv
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, ".")

from test_runner import (
    BASE_URL,
    QUERIES_CSV,
    check_backend,
    check_documents,
    is_abstention,
    run_query,
)

REPORT_MD = Path(__file__).parent / ".." / "docs" / "ablation-results.md"

METHODS = ["hybrid", "dense", "bm25"]


def load_ablation_queries() -> list[dict]:
    """Load 5 factual + 5 out-of-scope queries for ablation."""
    factual = []
    out_of_scope = []

    with open(QUERIES_CSV, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            cat = row["category"].strip().lower()
            if cat == "factual" and len(factual) < 5:
                factual.append(row)
            elif cat in ("out_of_scope", "adversarial") and len(out_of_scope) < 5:
                out_of_scope.append(row)

    return factual + out_of_scope


def run_method(queries: list[dict], method: str, delay: float = 5.0) -> list[dict]:
    results = []
    total = len(queries)

    for i, row in enumerate(queries, 1):
        qid = row["query_id"]
        query = row["query"]
        answer_in_doc = row["answer_in_document"].strip().lower()

        print(f"  [{method}] [{i}/{total}] Q{qid}: {query[:50]}...")

        result = run_query(query, method=method)

        if "error" in result:
            results.append({
                "query_id": qid,
                "query": query,
                "method": method,
                "answer_in_document": answer_in_doc,
                "error": True,
                "answered_correctly": False,
                "abstained": False,
                "correct_abstention": False,
                "latency_ms": 0,
                "input_tokens": 0,
                "output_tokens": 0,
            })
            print(f"           -> ERROR")
        else:
            answer = result.get("answer", "")
            abstained = is_abstention(answer)
            timings = result.get("timings", {})
            tokens = result.get("tokens_used", {})

            if answer_in_doc == "no":
                correct = abstained
                correct_abstention = abstained
            else:
                correct = not abstained
                correct_abstention = False

            results.append({
                "query_id": qid,
                "query": query,
                "method": method,
                "answer_in_document": answer_in_doc,
                "error": False,
                "answered_correctly": correct,
                "abstained": abstained,
                "correct_abstention": correct_abstention,
                "latency_ms": timings.get("total_ms", 0),
                "input_tokens": tokens.get("input_tokens", 0),
                "output_tokens": tokens.get("output_tokens", 0),
            })

            status = "CORRECT" if correct else "WRONG"
            print(f"           -> {status} | {'abstained' if abstained else 'answered'} | {timings.get('total_ms', 0)}ms")

        if i < total:
            time.sleep(delay)

    return results


def generate_report(all_results: dict[str, list[dict]]):
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    rows = []
    for method in METHODS:
        results = all_results.get(method, [])
        valid = [r for r in results if not r["error"]]

        factual = [r for r in valid if r["answer_in_document"] == "yes"]
        no_answer = [r for r in valid if r["answer_in_document"] == "no"]

        accuracy = sum(1 for r in factual if r["answered_correctly"])
        accuracy_rate = (accuracy / len(factual) * 100) if factual else 0

        abstention = sum(1 for r in no_answer if r["correct_abstention"])
        abstention_rate = (abstention / len(no_answer) * 100) if no_answer else 0

        overall = sum(1 for r in valid if r["answered_correctly"])
        overall_rate = (overall / len(valid) * 100) if valid else 0

        latencies = [r["latency_ms"] for r in valid if r["latency_ms"] > 0]
        avg_latency = statistics.mean(latencies) if latencies else 0

        rows.append({
            "method": method,
            "total": len(valid),
            "errors": len(results) - len(valid),
            "accuracy": accuracy,
            "accuracy_total": len(factual),
            "accuracy_rate": round(accuracy_rate, 1),
            "abstention": abstention,
            "abstention_total": len(no_answer),
            "abstention_rate": round(abstention_rate, 1),
            "overall_rate": round(overall_rate, 1),
            "avg_latency": round(avg_latency),
        })

    report = f"""# Ablation Study Results

**Date:** {timestamp}
**Queries:** 5 factual + 5 out-of-scope/adversarial per method
**Methods:** hybrid (dense+BM25), dense-only, BM25-only

## Summary

| Method | Accuracy (factual) | Abstention (no-answer) | Overall | Avg Latency |
|--------|-------------------|----------------------|---------|-------------|
"""

    for r in rows:
        report += (
            f"| {r['method']} "
            f"| {r['accuracy_rate']}% ({r['accuracy']}/{r['accuracy_total']}) "
            f"| {r['abstention_rate']}% ({r['abstention']}/{r['abstention_total']}) "
            f"| {r['overall_rate']}% "
            f"| {r['avg_latency']}ms |\n"
        )

    hybrid = next((r for r in rows if r["method"] == "hybrid"), None)
    dense = next((r for r in rows if r["method"] == "dense"), None)
    bm25 = next((r for r in rows if r["method"] == "bm25"), None)

    report += "\n## Analysis\n\n"

    if hybrid and dense:
        diff = hybrid["overall_rate"] - dense["overall_rate"]
        if diff > 0:
            report += f"- **Hybrid vs Dense-only:** Hybrid is {diff:.1f}% better overall, justifying BM25 integration\n"
        elif diff == 0:
            report += "- **Hybrid vs Dense-only:** No difference in accuracy — BM25 may not add value for this document\n"
        else:
            report += f"- **Hybrid vs Dense-only:** Dense-only is {-diff:.1f}% better — RRF merging may be diluting results\n"

    if hybrid and bm25:
        diff = hybrid["overall_rate"] - bm25["overall_rate"]
        if diff > 0:
            report += f"- **Hybrid vs BM25-only:** Hybrid is {diff:.1f}% better overall, justifying dense embeddings\n"
        elif diff == 0:
            report += "- **Hybrid vs BM25-only:** No difference in accuracy\n"
        else:
            report += f"- **Hybrid vs BM25-only:** BM25-only is {-diff:.1f}% better — semantic search may not help for this document\n"

    if dense and bm25:
        diff = dense["overall_rate"] - bm25["overall_rate"]
        if diff > 0:
            report += f"- **Dense vs BM25:** Dense is {diff:.1f}% better — semantic understanding adds value\n"
        elif diff == 0:
            report += "- **Dense vs BM25:** Tied — both approaches are equivalent for this test set\n"
        else:
            report += f"- **Dense vs BM25:** BM25 is {-diff:.1f}% better — keyword matching is sufficient for this document\n"

    report += """
## Detailed Results

### Per-Query Breakdown

| Query ID | Query | Hybrid | Dense | BM25 |
|----------|-------|--------|-------|------|
"""

    query_ids = sorted(set(r["query_id"] for results in all_results.values() for r in results))
    for qid in query_ids:
        query_text = ""
        method_results = {}
        for method in METHODS:
            for r in all_results.get(method, []):
                if r["query_id"] == qid:
                    query_text = r["query"][:40]
                    if r["error"]:
                        method_results[method] = "ERROR"
                    elif r["answered_correctly"]:
                        method_results[method] = "CORRECT"
                    else:
                        method_results[method] = "WRONG"

        h = method_results.get("hybrid", "N/A")
        d = method_results.get("dense", "N/A")
        b = method_results.get("bm25", "N/A")
        report += f"| {qid} | {query_text} | {h} | {d} | {b} |\n"

    best = max(rows, key=lambda r: r["overall_rate"]) if rows else None
    if best:
        report += f"""
## Conclusion

**Best method: {best['method']}** with {best['overall_rate']}% overall accuracy.

"""
        if best["method"] == "hybrid":
            report += "Hybrid retrieval (dense + BM25) provides the best results, justifying the additional complexity of maintaining both retrieval paths and RRF merging.\n"
        elif best["method"] == "dense":
            report += "Dense retrieval alone is sufficient. BM25 integration adds complexity without improving accuracy for this document type.\n"
        else:
            report += "BM25 keyword matching outperforms semantic search for this document. This may change with longer, more complex documents where semantic understanding matters more.\n"

    with open(REPORT_MD, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\nReport written to: {REPORT_MD}")


def main():
    parser = argparse.ArgumentParser(description="FARE Ablation Studies")
    parser.add_argument("--delay", type=float, default=5.0, help="Delay between queries (seconds)")
    parser.add_argument("--dry-run", action="store_true", help="Show plan without running")
    args = parser.parse_args()

    print("=" * 60)
    print("Phase 4.4: Ablation Studies")
    print("=" * 60)

    if not check_backend():
        print(f"\nERROR: Backend not running at {BASE_URL}")
        sys.exit(1)

    docs = check_documents()
    if not docs:
        print("\nERROR: No documents ingested.")
        sys.exit(1)

    queries = load_ablation_queries()
    total_calls = len(queries) * len(METHODS)
    factual = sum(1 for q in queries if q["answer_in_document"].strip().lower() == "yes")
    no_answer = len(queries) - factual
    print(f"Backend: OK | Documents: {len(docs)}")
    print(f"Queries: {len(queries)} ({factual} factual, {no_answer} no-answer)")
    print(f"Methods: {METHODS} | Total API calls: {total_calls}")

    if args.dry_run:
        print("\n--- DRY RUN ---")
        for method in METHODS:
            print(f"\n  Method: {method}")
            for row in queries:
                print(f"    Q{row['query_id']} [{row['answer_in_document']}] {row['query'][:50]}")
        return

    all_results = {}
    for method in METHODS:
        print(f"\n--- Running with method={method} ---")
        all_results[method] = run_method(queries, method, delay=args.delay)
        if method != METHODS[-1]:
            print("  Waiting 20s before next method...")
            time.sleep(20)

    generate_report(all_results)

    print("\n" + "=" * 60)
    print("ABLATION SUMMARY")
    print("=" * 60)
    for method in METHODS:
        results = all_results.get(method, [])
        valid = [r for r in results if not r["error"]]
        correct = sum(1 for r in valid if r["answered_correctly"])
        print(f"  {method:8s}: {correct}/{len(valid)} correct")
    print("=" * 60)


if __name__ == "__main__":
    main()
