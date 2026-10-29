"""
Phase 4.3 — Context Efficiency Analysis

Runs factual queries at different K values (3, 5, 7, 10) to find the optimal
number of retrieved chunks. Measures tokens, latency, and answer quality.

Usage:
    python -I eval_context_efficiency.py
    python -I eval_context_efficiency.py --queries 3    # fewer queries per K
    python -I eval_context_efficiency.py --delay 10
    python -I eval_context_efficiency.py --dry-run
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

REPORT_MD = Path(__file__).parent / ".." / "docs" / "context-efficiency.md"

K_VALUES = [3, 5, 7, 10]

GEMINI_FLASH_INPUT_COST = 0.10 / 1_000_000
GEMINI_FLASH_OUTPUT_COST = 0.40 / 1_000_000


def load_factual_queries(limit: int = 5) -> list[dict]:
    rows = []
    with open(QUERIES_CSV, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["category"].strip().lower() == "factual":
                rows.append(row)
                if len(rows) >= limit:
                    break
    return rows


def run_at_k(queries: list[dict], k: int, delay: float = 5.0) -> list[dict]:
    results = []
    total = len(queries)

    for i, row in enumerate(queries, 1):
        qid = row["query_id"]
        query = row["query"]

        print(f"  [K={k}] [{i}/{total}] Q{qid}: {query[:50]}...")

        result = run_query(query, k=k)

        if "error" in result:
            results.append({
                "query_id": qid,
                "query": query,
                "k": k,
                "error": True,
                "answered": False,
                "abstained": False,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_ms": 0,
                "retrieval_ms": 0,
                "generation_ms": 0,
                "num_sources": 0,
            })
            print(f"           -> ERROR")
        else:
            answer = result.get("answer", "")
            abstained = is_abstention(answer)
            tokens = result.get("tokens_used", {})
            timings = result.get("timings", {})
            sources = result.get("sources", [])

            results.append({
                "query_id": qid,
                "query": query,
                "k": k,
                "error": False,
                "answered": not abstained,
                "abstained": abstained,
                "input_tokens": tokens.get("input_tokens", 0),
                "output_tokens": tokens.get("output_tokens", 0),
                "total_ms": timings.get("total_ms", 0),
                "retrieval_ms": timings.get("retrieval_ms", 0),
                "generation_ms": timings.get("generation_ms", 0),
                "num_sources": len(sources),
            })
            status = "ABSTAIN" if abstained else "ANSWER"
            print(f"           -> {status} | {tokens.get('input_tokens', 0)} in / {tokens.get('output_tokens', 0)} out | {timings.get('total_ms', 0)}ms")

        if i < total:
            time.sleep(delay)

    return results


def generate_report(all_results: dict[int, list[dict]], num_queries: int):
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    rows = []
    for k in K_VALUES:
        results = all_results.get(k, [])
        valid = [r for r in results if not r["error"]]

        if not valid:
            rows.append({
                "k": k, "queries": len(results), "answered": 0,
                "answer_rate": 0, "avg_input": 0, "avg_output": 0,
                "avg_latency": 0, "avg_retrieval": 0, "avg_generation": 0,
                "cost_per_query": 0, "sources_returned": 0,
            })
            continue

        answered = sum(1 for r in valid if r["answered"])
        input_tokens = [r["input_tokens"] for r in valid if r["input_tokens"] > 0]
        output_tokens = [r["output_tokens"] for r in valid if r["output_tokens"] > 0]
        latencies = [r["total_ms"] for r in valid if r["total_ms"] > 0]
        retrieval_times = [r["retrieval_ms"] for r in valid if r["retrieval_ms"] > 0]
        generation_times = [r["generation_ms"] for r in valid if r["generation_ms"] > 0]

        avg_in = statistics.mean(input_tokens) if input_tokens else 0
        avg_out = statistics.mean(output_tokens) if output_tokens else 0
        cost = avg_in * GEMINI_FLASH_INPUT_COST + avg_out * GEMINI_FLASH_OUTPUT_COST

        rows.append({
            "k": k,
            "queries": len(valid),
            "answered": answered,
            "answer_rate": round(answered / len(valid) * 100, 1) if valid else 0,
            "avg_input": round(avg_in),
            "avg_output": round(avg_out),
            "avg_latency": round(statistics.mean(latencies)) if latencies else 0,
            "avg_retrieval": round(statistics.mean(retrieval_times)) if retrieval_times else 0,
            "avg_generation": round(statistics.mean(generation_times)) if generation_times else 0,
            "cost_per_query": cost,
            "sources_returned": round(statistics.mean(r["num_sources"] for r in valid)),
        })

    report = f"""# Context Efficiency Analysis

**Date:** {timestamp}
**Queries per K:** {num_queries} (factual queries only)
**Cost model:** Gemini Flash ($0.10/1M input, $0.40/1M output)

## Results by K

| K | Queries | Answer Rate | Avg Input Tokens | Avg Output Tokens | Avg Latency | Avg Retrieval | Avg Generation | Cost/Query | Sources |
|---|---------|-------------|-----------------|-------------------|-------------|---------------|----------------|------------|---------|
"""

    for r in rows:
        report += (
            f"| {r['k']} | {r['queries']} | {r['answer_rate']}% "
            f"| {r['avg_input']} | {r['avg_output']} "
            f"| {r['avg_latency']}ms | {r['avg_retrieval']}ms | {r['avg_generation']}ms "
            f"| ${r['cost_per_query']:.6f} | {r['sources_returned']} |\n"
        )

    best = None
    for r in rows:
        if r["answer_rate"] > 0:
            if best is None or (r["answer_rate"] >= best["answer_rate"] and r["avg_input"] <= best["avg_input"]):
                best = r

    if best:
        report += f"""
## Recommendation

**Optimal K = {best['k']}**

- Answer rate: {best['answer_rate']}%
- Avg input tokens: {best['avg_input']}
- Cost per query: ${best['cost_per_query']:.6f}
- At 1,000 queries/day: ${best['cost_per_query'] * 1000:.2f}/day

"""
    else:
        report += "\n## Recommendation\n\nInsufficient data to recommend an optimal K.\n"

    report += """## Analysis

- More chunks (higher K) means more context tokens sent to the LLM
- Diminishing returns: accuracy plateaus while cost grows linearly
- Retrieval latency increases slightly with K; generation latency increases with token count
- The sweet spot balances accuracy, cost, and latency

## Cost Projections

| Usage Level | K=3 Cost/day | K=5 Cost/day | K=10 Cost/day |
|-------------|-------------|-------------|--------------|
"""

    for label, daily in [("Light (100 queries)", 100), ("Medium (1K queries)", 1000), ("Heavy (10K queries)", 10000)]:
        costs = []
        for r in rows:
            costs.append(f"${r['cost_per_query'] * daily:.2f}")
        while len(costs) < 3:
            costs.append("N/A")
        k3, k5 = costs[0], costs[1]
        k10 = costs[3] if len(costs) > 3 else costs[-1]
        report += f"| {label} | {k3} | {k5} | {k10} |\n"

    with open(REPORT_MD, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\nReport written to: {REPORT_MD}")


def main():
    parser = argparse.ArgumentParser(description="FARE Context Efficiency Analysis")
    parser.add_argument("--queries", type=int, default=5, help="Number of queries per K value")
    parser.add_argument("--delay", type=float, default=5.0, help="Delay between queries (seconds)")
    parser.add_argument("--dry-run", action="store_true", help="Show plan without running")
    args = parser.parse_args()

    print("=" * 60)
    print("Phase 4.3: Context Efficiency Analysis")
    print("=" * 60)

    if not check_backend():
        print(f"\nERROR: Backend not running at {BASE_URL}")
        sys.exit(1)

    docs = check_documents()
    if not docs:
        print("\nERROR: No documents ingested.")
        sys.exit(1)

    queries = load_factual_queries(limit=args.queries)
    total_calls = len(queries) * len(K_VALUES)
    print(f"Backend: OK | Documents: {len(docs)}")
    print(f"Queries: {len(queries)} | K values: {K_VALUES} | Total API calls: {total_calls}")

    if args.dry_run:
        print("\n--- DRY RUN ---")
        for k in K_VALUES:
            print(f"\n  K={k}:")
            for row in queries:
                print(f"    Q{row['query_id']} {row['query'][:50]}")
        return

    all_results = {}
    for k in K_VALUES:
        print(f"\n--- Running with K={k} ---")
        all_results[k] = run_at_k(queries, k, delay=args.delay)
        if k != K_VALUES[-1]:
            print("  Waiting 15s before next K value...")
            time.sleep(15)

    generate_report(all_results, args.queries)

    print("\n" + "=" * 60)
    print("CONTEXT EFFICIENCY SUMMARY")
    print("=" * 60)
    for k in K_VALUES:
        results = all_results.get(k, [])
        valid = [r for r in results if not r["error"]]
        answered = sum(1 for r in valid if r["answered"])
        avg_in = statistics.mean(r["input_tokens"] for r in valid if r["input_tokens"] > 0) if any(r["input_tokens"] > 0 for r in valid) else 0
        print(f"  K={k:2d}: {answered}/{len(valid)} answered | ~{avg_in:.0f} input tokens")
    print("=" * 60)


if __name__ == "__main__":
    main()
