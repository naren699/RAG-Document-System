"""
Phase 4.1 — Abstention Rate Evaluation

Measures how often the system correctly refuses to answer when the answer
is not in the document. Target: >= 90%.

Usage:
    python -I eval_abstention.py
    python -I eval_abstention.py --delay 10
    python -I eval_abstention.py --dry-run
"""

import argparse
import csv
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, ".")

from test_runner import (
    BASE_URL,
    QUERIES_CSV,
    ABSTAIN_PHRASES,
    check_backend,
    check_documents,
    is_abstention,
    run_query,
)

RESULTS_CSV = Path(__file__).parent / ".." / "docs" / "abstention-results.csv"


def load_no_answer_queries() -> list[dict]:
    rows = []
    with open(QUERIES_CSV, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["answer_in_document"].strip().lower() == "no":
                rows.append(row)
    return rows


def run_abstention_eval(queries: list[dict], delay: float = 5.0) -> list[dict]:
    results = []
    total = len(queries)

    for i, row in enumerate(queries, 1):
        qid = row["query_id"]
        query = row["query"]
        category = row["category"]

        print(f"[{i}/{total}] Q{qid} ({category}): {query[:60]}...")

        result = run_query(query)

        if "error" in result:
            answer = result["error"]
            refusal = False
            status = "ERROR"
        else:
            answer = result.get("answer", "")
            refusal = is_abstention(answer)
            status = "REFUSAL" if refusal else "ANSWERED (bad)"

        print(f"       -> {status}: {answer[:80]}...")

        results.append({
            "query_id": qid,
            "query": query,
            "category": category,
            "system_response": answer,
            "is_correct_refusal": refusal,
            "latency_ms": result.get("timings", {}).get("total_ms", 0),
            "input_tokens": result.get("tokens_used", {}).get("input_tokens", 0),
            "output_tokens": result.get("tokens_used", {}).get("output_tokens", 0),
        })

        if i < total:
            time.sleep(delay)

    return results


def write_results(results: list[dict]):
    if not results:
        return
    with open(RESULTS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)
    print(f"\nResults written to: {RESULTS_CSV}")


def print_summary(results: list[dict]):
    valid = [r for r in results if r["is_correct_refusal"] is not False or r["system_response"][:5] != "HTTP "]
    non_error = [r for r in results if not r["system_response"].startswith("HTTP ")]
    correct = sum(1 for r in non_error if r["is_correct_refusal"])
    total = len(non_error)
    errors = len(results) - len(non_error)
    rate = (correct / total * 100) if total else 0

    print("\n" + "=" * 60)
    print("ABSTENTION RATE EVALUATION")
    print("=" * 60)
    print(f"  Total queries:       {len(results)}")
    print(f"  Errors:              {errors}")
    print(f"  Correct refusals:    {correct}/{total}")
    print(f"  Abstention Rate:     {rate:.1f}%")
    print(f"  Target:              >= 90%")
    print(f"  Status:              {'PASS' if rate >= 90 else 'FAIL'}")
    print("=" * 60)

    return {
        "total": len(results),
        "errors": errors,
        "correct_refusals": correct,
        "evaluated": total,
        "abstention_rate": round(rate, 1),
    }


def main():
    parser = argparse.ArgumentParser(description="FARE Abstention Rate Evaluation")
    parser.add_argument("--delay", type=float, default=5.0, help="Delay between queries (seconds)")
    parser.add_argument("--dry-run", action="store_true", help="Show queries without running")
    args = parser.parse_args()

    print("=" * 60)
    print("Phase 4.1: Abstention Rate Evaluation")
    print("=" * 60)

    if not check_backend():
        print(f"\nERROR: Backend not running at {BASE_URL}")
        sys.exit(1)

    docs = check_documents()
    if not docs:
        print("\nERROR: No documents ingested.")
        sys.exit(1)

    queries = load_no_answer_queries()
    print(f"Backend: OK | Documents: {len(docs)} | No-answer queries: {len(queries)}")

    if args.dry_run:
        print("\n--- DRY RUN ---")
        for row in queries:
            print(f"  Q{row['query_id']} [{row['category']}] {row['query']}")
        return

    print()
    results = run_abstention_eval(queries, delay=args.delay)
    write_results(results)
    return print_summary(results)


if __name__ == "__main__":
    main()
