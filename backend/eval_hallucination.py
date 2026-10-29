"""
Phase 4.2 — Hallucination Score Evaluation

Measures how often system answers are supported by the retrieved context.
Target: >= 85%.

Uses a heuristic: extracts key factual tokens (numbers, proper nouns, dates)
from the answer and checks if they appear in source chunks. Results are also
flagged for manual review.

Usage:
    python -I eval_hallucination.py
    python -I eval_hallucination.py --delay 10
    python -I eval_hallucination.py --dry-run
"""

import argparse
import csv
import re
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

RESULTS_CSV = Path(__file__).parent / ".." / "docs" / "hallucination-results.csv"


def load_answer_present_queries() -> list[dict]:
    rows = []
    with open(QUERIES_CSV, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["answer_in_document"].strip().lower() == "yes":
                rows.append(row)
    return rows


def extract_factual_claims(text: str) -> list[str]:
    """Extract numbers, years, percentages, and capitalized terms from text."""
    claims = []
    claims.extend(re.findall(r"\b\d{4}\b", text))
    claims.extend(re.findall(r"\b\d+\.?\d*%?\b", text))
    claims.extend(re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", text))
    return list(set(claims))


def check_faithfulness(answer: str, source_texts: list[str]) -> dict:
    """Heuristic check: are factual claims in the answer supported by sources?"""
    if is_abstention(answer):
        return {
            "auto_faithful": True,
            "needs_manual_review": False,
            "unsupported_claims": [],
            "notes": "System abstained (no claims to verify)",
        }

    combined_sources = " ".join(source_texts).lower()
    claims = extract_factual_claims(answer)

    if not claims:
        return {
            "auto_faithful": True,
            "needs_manual_review": True,
            "unsupported_claims": [],
            "notes": "No extractable factual claims; needs manual review",
        }

    unsupported = []
    for claim in claims:
        if claim.lower() not in combined_sources:
            unsupported.append(claim)

    if not unsupported:
        return {
            "auto_faithful": True,
            "needs_manual_review": False,
            "unsupported_claims": [],
            "notes": "All extracted claims found in source chunks",
        }

    ratio = len(unsupported) / len(claims)
    if ratio > 0.5:
        return {
            "auto_faithful": False,
            "needs_manual_review": True,
            "unsupported_claims": unsupported,
            "notes": f"{len(unsupported)}/{len(claims)} claims not in sources: {unsupported[:5]}",
        }

    return {
        "auto_faithful": True,
        "needs_manual_review": True,
        "unsupported_claims": unsupported,
        "notes": f"{len(unsupported)}/{len(claims)} minor claims not in sources (may be paraphrased): {unsupported[:5]}",
    }


def run_hallucination_eval(queries: list[dict], delay: float = 5.0) -> list[dict]:
    results = []
    total = len(queries)

    for i, row in enumerate(queries, 1):
        qid = row["query_id"]
        query = row["query"]
        category = row["category"]

        print(f"[{i}/{total}] Q{qid} ({category}): {query[:60]}...")

        result = run_query(query)

        if "error" in result:
            results.append({
                "query_id": qid,
                "query": query,
                "category": category,
                "answer": result["error"],
                "source_texts": "",
                "auto_faithful": "error",
                "needs_manual_review": True,
                "unsupported_claims": "",
                "notes": result["error"],
                "latency_ms": 0,
                "input_tokens": 0,
                "output_tokens": 0,
            })
            print(f"       -> ERROR: {result['error'][:80]}")
        else:
            answer = result.get("answer", "")
            sources = result.get("sources", [])
            source_texts = [s.get("text", "") for s in sources]
            combined = " | ".join(f"[p{s.get('page_num', '?')}] {s.get('text', '')[:100]}" for s in sources)

            check = check_faithfulness(answer, source_texts)
            status = "FAITHFUL" if check["auto_faithful"] else "HALLUCINATED"
            review = " (needs review)" if check["needs_manual_review"] else ""

            print(f"       -> {status}{review}: {answer[:80]}...")

            results.append({
                "query_id": qid,
                "query": query,
                "category": category,
                "answer": answer,
                "source_texts": combined[:500],
                "auto_faithful": check["auto_faithful"],
                "needs_manual_review": check["needs_manual_review"],
                "unsupported_claims": ", ".join(check["unsupported_claims"][:10]),
                "notes": check["notes"],
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
    non_error = [r for r in results if r["auto_faithful"] != "error"]
    errors = len(results) - len(non_error)

    faithful = sum(1 for r in non_error if r["auto_faithful"] is True)
    hallucinated = sum(1 for r in non_error if r["auto_faithful"] is False)
    needs_review = sum(1 for r in non_error if r["needs_manual_review"])
    total = len(non_error)
    score = (faithful / total * 100) if total else 0

    print("\n" + "=" * 60)
    print("HALLUCINATION SCORE EVALUATION")
    print("=" * 60)
    print(f"  Total queries:       {len(results)}")
    print(f"  Errors:              {errors}")
    print(f"  Auto-faithful:       {faithful}/{total}")
    print(f"  Auto-hallucinated:   {hallucinated}/{total}")
    print(f"  Needs manual review: {needs_review}/{total}")
    print(f"  Hallucination Score: {score:.1f}%")
    print(f"  Target:              >= 85%")
    print(f"  Status:              {'PASS' if score >= 85 else 'NEEDS REVIEW'}")
    print("=" * 60)

    return {
        "total": len(results),
        "errors": errors,
        "faithful": faithful,
        "hallucinated": hallucinated,
        "needs_review": needs_review,
        "evaluated": total,
        "hallucination_score": round(score, 1),
    }


def main():
    parser = argparse.ArgumentParser(description="FARE Hallucination Score Evaluation")
    parser.add_argument("--delay", type=float, default=5.0, help="Delay between queries (seconds)")
    parser.add_argument("--dry-run", action="store_true", help="Show queries without running")
    args = parser.parse_args()

    print("=" * 60)
    print("Phase 4.2: Hallucination Score Evaluation")
    print("=" * 60)

    if not check_backend():
        print(f"\nERROR: Backend not running at {BASE_URL}")
        sys.exit(1)

    docs = check_documents()
    if not docs:
        print("\nERROR: No documents ingested.")
        sys.exit(1)

    queries = load_answer_present_queries()
    print(f"Backend: OK | Documents: {len(docs)} | Answer-present queries: {len(queries)}")

    if args.dry_run:
        print("\n--- DRY RUN ---")
        for row in queries:
            print(f"  Q{row['query_id']} [{row['category']}] {row['query']}")
        return

    print()
    results = run_hallucination_eval(queries, delay=args.delay)
    write_results(results)
    return print_summary(results)


if __name__ == "__main__":
    main()
