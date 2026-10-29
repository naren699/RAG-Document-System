"""
Phase 3.9 Test Runner — runs test queries against the FARE backend and records results.

Usage:
    python -I test_runner.py                          # run all queries
    python -I test_runner.py --ingest path/to/file.pdf  # ingest a PDF first, then run
    python -I test_runner.py --category adversarial   # run only one category
    python -I test_runner.py --dry-run                # show queries without running

Requires: backend running at http://localhost:8000 with at least one document ingested.
Outputs:  ../docs/test-results.csv  and  ../docs/phase3-testing.md
"""

import argparse
import csv
import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

BASE_URL = "http://localhost:8000"
QUERIES_CSV = Path(__file__).parent / ".." / "docs" / "test-queries.csv"
RESULTS_CSV = Path(__file__).parent / ".." / "docs" / "test-results.csv"
REPORT_MD = Path(__file__).parent / ".." / "docs" / "phase3-testing.md"

ABSTAIN_PHRASES = [
    "i don't have that information",
    "not in the provided documents",
    "i cannot find",
    "the document does not",
    "no information about",
    "not mentioned in",
    "i don't know",
    "cannot answer",
    "not found in the",
    "the provided context does not",
    "is not discussed",
    "no relevant information",
]


def check_backend():
    try:
        r = httpx.get(f"{BASE_URL}/health", timeout=5)
        r.raise_for_status()
        return True
    except Exception:
        return False


def check_documents():
    r = httpx.get(f"{BASE_URL}/api/documents", timeout=10)
    r.raise_for_status()
    docs = r.json().get("documents", [])
    return docs


def ingest_pdf(pdf_path: str):
    print(f"Ingesting: {pdf_path}")
    with open(pdf_path, "rb") as f:
        r = httpx.post(
            f"{BASE_URL}/api/ingest",
            files={"file": (Path(pdf_path).name, f, "application/pdf")},
            timeout=120,
        )
    r.raise_for_status()
    result = r.json()
    print(f"  -> {result['chunks_count']} chunks created ({result['text_chunks']} text, {result.get('visual_chunks', 0)} visual)")
    return result


def is_abstention(answer: str) -> bool:
    lower = answer.lower()
    return any(phrase in lower for phrase in ABSTAIN_PHRASES)


def run_query(query: str, method: str = "hybrid", k: int = 5, retrieval_only: bool = False, max_retries: int = 3) -> dict:
    endpoint = "/api/retrieve" if retrieval_only else "/api/query"
    for attempt in range(max_retries + 1):
        start = time.time()
        try:
            r = httpx.post(
                f"{BASE_URL}{endpoint}",
                json={"query": query, "method": method, "k": k},
                timeout=90,
            )
            elapsed = time.time() - start
            is_retryable = r.status_code in (429, 503) or (r.status_code == 500 and ("rate" in r.text.lower() or "unavailable" in r.text.lower() or "high demand" in r.text.lower()))
            if is_retryable:
                wait = 10 * (attempt + 1)
                if attempt < max_retries:
                    print(f"       Rate limited (HTTP {r.status_code}), retrying in {wait}s (attempt {attempt + 1}/{max_retries})...")
                    time.sleep(wait)
                    continue
                return {"error": f"HTTP {r.status_code} after {max_retries} retries", "elapsed_s": round(elapsed, 2)}
            if r.status_code != 200:
                return {"error": f"HTTP {r.status_code}: {r.text}", "elapsed_s": round(elapsed, 2)}
            data = r.json()
            data["elapsed_s"] = round(elapsed, 2)
            if retrieval_only:
                data["sources"] = data.get("chunks", [])
                data["answer"] = "(retrieval only — no LLM call)"
                data["provider"] = "none"
                data["model"] = "none"
                data["tokens_used"] = {"input_tokens": 0, "output_tokens": 0}
                data["timings"] = {"retrieval_ms": int(elapsed * 1000), "generation_ms": 0, "total_ms": int(elapsed * 1000)}
            return data
        except Exception as e:
            elapsed = time.time() - start
            if attempt < max_retries:
                wait = 10 * (attempt + 1)
                print(f"       Error: {e}, retrying in {wait}s...")
                time.sleep(wait)
                continue
            return {"error": str(e), "elapsed_s": round(elapsed, 2)}


def evaluate_result(row: dict, result: dict) -> dict:
    if "error" in result:
        return {
            "is_correct": "error",
            "hallucination_detected": "unknown",
            "abstained": False,
            "max_relevance": 0,
            "avg_relevance": 0,
            "notes": result["error"],
        }

    answer = result.get("answer", "")
    abstained = is_abstention(answer)
    answer_in_doc = row["answer_in_document"].strip().lower()
    category = row["category"].strip().lower()

    if answer_in_doc == "no":
        is_correct = "yes" if abstained else "no"
        hallucination = "no" if abstained else "likely"
    elif answer_in_doc == "yes":
        is_correct = "likely" if not abstained else "no"
        hallucination = "no"
    else:
        is_correct = "needs_review"
        hallucination = "needs_review"

    sources = result.get("sources", [])
    max_score = max((s.get("score", 0) for s in sources), default=0)
    avg_score = statistics.mean(s.get("score", 0) for s in sources) if sources else 0

    return {
        "is_correct": is_correct,
        "hallucination_detected": hallucination,
        "abstained": abstained,
        "max_relevance": round(max_score, 3),
        "avg_relevance": round(avg_score, 3),
        "notes": "",
    }


def load_queries(category_filter: str = None) -> list[dict]:
    rows = []
    with open(QUERIES_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if category_filter and row["category"].strip().lower() != category_filter.lower():
                continue
            rows.append(row)
    return rows


def run_all(queries: list[dict], delay: float = 1.0, retrieval_only: bool = False) -> list[dict]:
    results = []
    total = len(queries)

    for i, row in enumerate(queries, 1):
        qid = row["query_id"]
        query = row["query"]
        category = row["category"]

        print(f"[{i}/{total}] Q{qid} ({category}): {query[:60]}...")

        result = run_query(query, retrieval_only=retrieval_only)
        evaluation = evaluate_result(row, result)

        answer = result.get("answer", result.get("error", ""))[:200]
        timings = result.get("timings", {})
        tokens = result.get("tokens_used", {})

        entry = {
            "query_id": qid,
            "query": query,
            "category": category,
            "answer_in_document": row["answer_in_document"],
            "answer_preview": answer,
            "is_correct": evaluation["is_correct"],
            "hallucination_detected": evaluation["hallucination_detected"],
            "abstained": evaluation["abstained"],
            "max_relevance": evaluation["max_relevance"],
            "avg_relevance": evaluation["avg_relevance"],
            "retrieval_ms": timings.get("retrieval_ms", 0),
            "generation_ms": timings.get("generation_ms", 0),
            "total_ms": timings.get("total_ms", 0),
            "input_tokens": tokens.get("input_tokens", 0),
            "output_tokens": tokens.get("output_tokens", 0),
            "provider": result.get("provider", ""),
            "model": result.get("model", ""),
            "notes": evaluation["notes"],
        }
        results.append(entry)

        status = "ABSTAIN" if evaluation["abstained"] else "ANSWER"
        correctness = evaluation["is_correct"]
        print(f"       -> {status} | correct={correctness} | relevance={evaluation['max_relevance']} | {timings.get('total_ms', '?')}ms")

        if i < total:
            time.sleep(delay)

    return results


def write_results_csv(results: list[dict]):
    if not results:
        return
    fieldnames = results[0].keys()
    with open(RESULTS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    print(f"\nResults written to: {RESULTS_CSV}")


def generate_report(results: list[dict], documents: list[dict]):
    total = len(results)
    if total == 0:
        return

    errors = [r for r in results if r["is_correct"] == "error"]
    valid = [r for r in results if r["is_correct"] != "error"]

    out_of_scope = [r for r in valid if r["answer_in_document"] == "no"]
    in_scope = [r for r in valid if r["answer_in_document"] == "yes"]
    adversarial = [r for r in valid if r["category"] == "adversarial"]

    abstention_correct = sum(1 for r in out_of_scope if r["abstained"])
    abstention_total = len(out_of_scope)
    abstention_rate = (abstention_correct / abstention_total * 100) if abstention_total else 0

    hallucination_count = sum(1 for r in valid if r["hallucination_detected"] == "likely")
    hallucination_rate = (hallucination_count / len(valid) * 100) if valid else 0
    hallucination_score = 100 - hallucination_rate

    in_scope_correct = sum(1 for r in in_scope if r["is_correct"] == "likely")
    in_scope_rate = (in_scope_correct / len(in_scope) * 100) if in_scope else 0

    latencies = [r["total_ms"] for r in valid if r["total_ms"] > 0]
    retrieval_times = [r["retrieval_ms"] for r in valid if r["retrieval_ms"] > 0]
    generation_times = [r["generation_ms"] for r in valid if r["generation_ms"] > 0]

    avg_latency = statistics.mean(latencies) if latencies else 0
    p50_latency = statistics.median(latencies) if latencies else 0
    p95_latency = sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0
    max_latency = max(latencies) if latencies else 0

    avg_retrieval = statistics.mean(retrieval_times) if retrieval_times else 0
    avg_generation = statistics.mean(generation_times) if generation_times else 0

    input_tokens = [r["input_tokens"] for r in valid if r["input_tokens"] > 0]
    output_tokens = [r["output_tokens"] for r in valid if r["output_tokens"] > 0]
    avg_input = statistics.mean(input_tokens) if input_tokens else 0
    avg_output = statistics.mean(output_tokens) if output_tokens else 0
    total_input = sum(input_tokens)
    total_output = sum(output_tokens)

    relevances = [r["max_relevance"] for r in valid if r["max_relevance"] > 0]
    avg_relevance = statistics.mean(relevances) if relevances else 0

    provider = valid[0]["provider"] if valid else "unknown"
    model = valid[0]["model"] if valid else "unknown"
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    doc_summary = "\n".join(f"  - `{d.get('doc_id', '?')}`: {d.get('chunks_count', '?')} chunks" for d in documents) if documents else "  - No documents found"

    report = f"""# Phase 3 Testing Report

**Date:** {timestamp}
**LLM Provider:** {provider}
**Model:** {model}
**Queries:** {total} ({len(in_scope)} in-scope, {len(out_of_scope)} out-of-scope, {len(adversarial)} adversarial, {len(errors)} errors)

## Documents Tested

{doc_summary}

## Key Metrics

| Metric | Value | Target |
|--------|-------|--------|
| Abstention Rate | {abstention_rate:.1f}% ({abstention_correct}/{abstention_total}) | >= 90% |
| Hallucination Score | {hallucination_score:.1f}% | >= 85% |
| In-Scope Accuracy | {in_scope_rate:.1f}% ({in_scope_correct}/{len(in_scope)}) | High |
| Avg Relevance Score | {avg_relevance:.3f} | > 0.5 |

## Latency

| Metric | Value |
|--------|-------|
| Average Total | {avg_latency:.0f} ms |
| Median (P50) | {p50_latency:.0f} ms |
| P95 | {p95_latency:.0f} ms |
| Max | {max_latency:.0f} ms |
| Avg Retrieval | {avg_retrieval:.0f} ms |
| Avg Generation | {avg_generation:.0f} ms |

## Token Usage

| Metric | Value |
|--------|-------|
| Avg Input Tokens | {avg_input:.0f} |
| Avg Output Tokens | {avg_output:.0f} |
| Total Input Tokens | {total_input} |
| Total Output Tokens | {total_output} |

## Results by Category

### Factual Queries (answer in document)

| ID | Query | Correct | Abstained | Relevance | Latency |
|----|-------|---------|-----------|-----------|---------|
"""

    for r in sorted(in_scope, key=lambda x: int(x["query_id"])):
        q = r["query"][:50]
        report += f"| {r['query_id']} | {q} | {r['is_correct']} | {r['abstained']} | {r['max_relevance']} | {r['total_ms']}ms |\n"

    report += """
### Out-of-Scope Queries (answer NOT in document)

| ID | Query | Abstained | Hallucination | Relevance | Latency |
|----|-------|-----------|---------------|-----------|---------|
"""

    for r in sorted(out_of_scope, key=lambda x: int(x["query_id"])):
        q = r["query"][:50]
        report += f"| {r['query_id']} | {q} | {r['abstained']} | {r['hallucination_detected']} | {r['max_relevance']} | {r['total_ms']}ms |\n"

    report += """
### Adversarial Queries

| ID | Query | Abstained | Hallucination | Relevance | Latency |
|----|-------|-----------|---------------|-----------|---------|
"""

    for r in sorted(adversarial, key=lambda x: int(x["query_id"])):
        q = r["query"][:50]
        report += f"| {r['query_id']} | {q} | {r['abstained']} | {r['hallucination_detected']} | {r['max_relevance']} | {r['total_ms']}ms |\n"

    if errors:
        report += """
### Errors

| ID | Query | Error |
|----|-------|-------|
"""
        for r in errors:
            q = r["query"][:50]
            note = r["notes"][:80]
            report += f"| {r['query_id']} | {q} | {note} |\n"

    report += f"""
## Observations

- **Abstention rate:** {abstention_rate:.1f}% — {"meets" if abstention_rate >= 90 else "below"} the 90% target
- **Hallucination score:** {hallucination_score:.1f}% — {"meets" if hallucination_score >= 85 else "below"} the 85% target
- **Latency:** average {avg_latency:.0f}ms — {"meets" if avg_latency < 10000 else "exceeds"} the 10s target
- **Token efficiency:** ~{avg_input:.0f} input tokens per query

## Known Limitations

- Evaluation is semi-automated: "is_correct" for in-scope queries is marked "likely" (not verified against ground truth)
- Hallucination detection relies on abstention pattern matching, not semantic verification
- Results depend on the specific PDF(s) ingested during testing
- BM25 index is rebuilt on startup; results may vary across restarts

## Next Steps

- [ ] Manual review of "likely correct" answers for actual correctness
- [ ] Add ground-truth answers to test-queries.csv for automated scoring
- [ ] Run ablation tests (Phase 4): dense-only vs BM25-only vs hybrid
- [ ] Test with multiple document types (reports, papers, manuals)
"""

    with open(REPORT_MD, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Report written to: {REPORT_MD}")


def main():
    parser = argparse.ArgumentParser(description="FARE Phase 3 Test Runner")
    parser.add_argument("--ingest", help="Path to PDF to ingest before testing")
    parser.add_argument("--category", help="Run only this category (factual, out_of_scope, adversarial, multi_chunk)")
    parser.add_argument("--delay", type=float, default=4.0, help="Delay between queries in seconds")
    parser.add_argument("--dry-run", action="store_true", help="Show queries without running them")
    parser.add_argument("--retrieval-only", action="store_true", help="Test retrieval only (skip LLM calls)")
    args = parser.parse_args()

    print("=" * 60)
    print("FARE Phase 3 Test Runner")
    print("=" * 60)

    if not check_backend():
        print("\nERROR: Backend is not running at", BASE_URL)
        print("Start it with: cd backend && python -I app.py")
        sys.exit(1)

    print("Backend: OK")

    if args.ingest:
        ingest_pdf(args.ingest)

    documents = check_documents()
    if not documents:
        print("\nERROR: No documents ingested. Use --ingest <pdf> or upload via the UI first.")
        sys.exit(1)

    print(f"Documents: {len(documents)}")
    for doc in documents:
        print(f"  - {doc.get('doc_id', '?')}: {doc.get('chunks_count', '?')} chunks")

    queries = load_queries(args.category)
    mode = "retrieval-only" if args.retrieval_only else "full pipeline"
    print(f"Queries: {len(queries)}" + (f" (category: {args.category})" if args.category else "") + f" | Mode: {mode}")

    if args.dry_run:
        print("\n--- DRY RUN ---")
        for row in queries:
            print(f"  Q{row['query_id']} [{row['category']}] {row['query']}")
        return

    print("\nRunning queries...\n")
    results = run_all(queries, delay=args.delay, retrieval_only=args.retrieval_only)

    write_results_csv(results)
    generate_report(results, documents)

    valid = [r for r in results if r["is_correct"] != "error"]
    out_of_scope = [r for r in valid if r["answer_in_document"] == "no"]
    abstained = sum(1 for r in out_of_scope if r["abstained"])
    hallucinations = sum(1 for r in valid if r["hallucination_detected"] == "likely")

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Total queries:     {len(results)}")
    print(f"  Errors:            {len(results) - len(valid)}")
    print(f"  Abstention rate:   {abstained}/{len(out_of_scope)} ({abstained / len(out_of_scope) * 100:.0f}%)" if out_of_scope else "  Abstention rate:   N/A")
    print(f"  Hallucinations:    {hallucinations}/{len(valid)}")
    latencies = [r["total_ms"] for r in valid if r["total_ms"] > 0]
    if latencies:
        print(f"  Avg latency:       {statistics.mean(latencies):.0f}ms")
        print(f"  Max latency:       {max(latencies)}ms")
    print("=" * 60)


if __name__ == "__main__":
    main()
