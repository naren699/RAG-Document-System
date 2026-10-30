"""Generate evaluation report from eval output CSVs."""

import csv
import statistics
import sys
from datetime import datetime
from pathlib import Path

DOCS_DIR = Path(__file__).parent.parent / "docs"


def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _pct(n: int, total: int) -> str:
    return f"{n / total * 100:.1f}%" if total else "N/A"


def _status(value: float, target: float, higher_is_better: bool = True) -> str:
    if higher_is_better:
        return "PASS" if value >= target else "FAIL"
    return "PASS" if value <= target else "FAIL"


def _section_summary(test_results: list[dict], manual_labels: list[dict],
                     abstention_results: list[dict]) -> str:
    lines = ["## Summary", "", "| Metric | Value | Target | Status |",
             "|--------|-------|--------|--------|"]

    total_queries = len(test_results)
    latencies = []
    for r in test_results:
        lat = r.get("latency_ms") or r.get("total_ms")
        if lat:
            try:
                latencies.append(float(lat))
            except ValueError:
                pass

    # Abstention rate from abstention results or manual labels
    abstention_rate = None
    if abstention_results:
        correct_abstentions = sum(1 for r in abstention_results
                                  if r.get("correct_abstention", "").lower() == "true")
        oos_total = sum(1 for r in abstention_results
                        if r.get("category", "") == "out_of_scope")
        if oos_total:
            abstention_rate = correct_abstentions / oos_total
    elif manual_labels:
        refusals = [r for r in manual_labels if r.get("label") in
                    ("correct_refusal", "wrong_refusal")]
        correct_refusals = sum(1 for r in refusals if r["label"] == "correct_refusal")
        if refusals:
            abstention_rate = correct_refusals / len(refusals)

    if abstention_rate is not None:
        lines.append(f"| Abstention Rate | {abstention_rate * 100:.1f}% | >= 90% | "
                     f"{_status(abstention_rate, 0.90)} |")
    else:
        lines.append("| Abstention Rate | N/A | >= 90% | — |")

    # Faithfulness from manual labels
    if manual_labels:
        faithful = sum(1 for r in manual_labels
                       if r.get("label") in ("correct", "correct_refusal"))
        faith_rate = faithful / len(manual_labels) if manual_labels else 0
        lines.append(f"| Faithfulness | {faith_rate * 100:.1f}% | >= 85% | "
                     f"{_status(faith_rate, 0.85)} |")
    else:
        lines.append("| Faithfulness | N/A | >= 85% | — |")

    # Avg latency
    if latencies:
        avg_lat = statistics.mean(latencies) / 1000
        lines.append(f"| Avg Latency | {avg_lat:.2f}s | < 5s | "
                     f"{_status(avg_lat, 5.0, higher_is_better=False)} |")
    else:
        lines.append("| Avg Latency | N/A | < 5s | — |")

    # Pass rate from manual labels
    if manual_labels:
        correct = sum(1 for r in manual_labels
                      if r.get("label") in ("correct", "correct_refusal"))
        lines.append(f"| Pass Rate | {_pct(correct, len(manual_labels))} | — | — |")

    lines.append(f"\nTotal queries evaluated: {total_queries}")
    return "\n".join(lines)


def _section_categories(test_results: list[dict], manual_labels: list[dict]) -> str:
    if not test_results:
        return ""

    labels_by_id = {}
    for r in manual_labels:
        qid = r.get("query_id", "")
        labels_by_id[qid] = r.get("label", "")

    categories: dict[str, dict] = {}
    for r in test_results:
        cat = r.get("category", "unknown")
        if cat not in categories:
            categories[cat] = {"total": 0, "correct": 0}
        categories[cat]["total"] += 1
        qid = r.get("query_id", "")
        if labels_by_id.get(qid) in ("correct", "correct_refusal"):
            categories[cat]["correct"] += 1

    lines = ["## Per-Category Breakdown", "",
             "| Category | Total | Correct | Accuracy |",
             "|----------|-------|---------|----------|"]
    for cat in sorted(categories):
        d = categories[cat]
        lines.append(f"| {cat} | {d['total']} | {d['correct']} | "
                     f"{_pct(d['correct'], d['total'])} |")
    return "\n".join(lines)


def _section_context_efficiency(rows: list[dict]) -> str:
    if not rows:
        return "\n## Context Efficiency\n\n*No context efficiency data available.*"

    lines = ["## Context Efficiency", "",
             "| K | Avg Tokens | Avg Latency (ms) | Avg Cost ($) |",
             "|---|-----------|------------------|-------------|"]
    for r in rows:
        k = r.get("k", "?")
        tokens = r.get("avg_tokens", "?")
        latency = r.get("avg_latency_ms", "?")
        cost = r.get("avg_cost", "?")
        lines.append(f"| {k} | {tokens} | {latency} | {cost} |")
    return "\n".join(lines)


def _section_ablation(rows: list[dict]) -> str:
    if not rows:
        return "\n## Ablation Study\n\n*No ablation data available.*"

    lines = ["## Ablation Study", "",
             "| Method | Avg Score | Avg Latency (ms) | Queries |",
             "|--------|----------|------------------|---------|"]
    for r in rows:
        method = r.get("method", "?")
        score = r.get("avg_score", r.get("avg_relevance", "?"))
        latency = r.get("avg_latency_ms", "?")
        queries = r.get("num_queries", r.get("total", "?"))
        lines.append(f"| {method} | {score} | {latency} | {queries} |")
    return "\n".join(lines)


def _section_latency(test_results: list[dict]) -> str:
    latencies = []
    for r in test_results:
        lat = r.get("latency_ms") or r.get("total_ms")
        if lat:
            try:
                latencies.append(float(lat))
            except ValueError:
                pass

    if not latencies:
        return "\n## Latency Distribution\n\n*No latency data available.*"

    latencies.sort()
    n = len(latencies)

    def percentile(p: float) -> float:
        idx = int(p / 100 * n)
        return latencies[min(idx, n - 1)]

    lines = ["## Latency Distribution", "",
             f"- **P50**: {percentile(50):.0f}ms ({percentile(50) / 1000:.2f}s)",
             f"- **P90**: {percentile(90):.0f}ms ({percentile(90) / 1000:.2f}s)",
             f"- **P99**: {percentile(99):.0f}ms ({percentile(99) / 1000:.2f}s)",
             f"- **Min**: {min(latencies):.0f}ms",
             f"- **Max**: {max(latencies):.0f}ms",
             f"- **Mean**: {statistics.mean(latencies):.0f}ms",
             f"- **Queries**: {n}"]
    return "\n".join(lines)


def generate_report() -> str:
    test_results = _read_csv(DOCS_DIR / "test-results.csv")
    manual_labels = _read_csv(DOCS_DIR / "manual-labels.csv")
    abstention_results = _read_csv(DOCS_DIR / "abstention-results.csv")
    hallucination_results = _read_csv(DOCS_DIR / "hallucination-results.csv")
    context_eff = _read_csv(DOCS_DIR / "context-efficiency-results.csv")
    ablation = _read_csv(DOCS_DIR / "ablation-results.csv")

    sections = [
        f"# FARE Evaluation Report",
        f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        _section_summary(test_results, manual_labels, abstention_results),
        "",
        _section_categories(test_results, manual_labels),
        "",
        _section_context_efficiency(context_eff),
        "",
        _section_ablation(ablation),
        "",
        _section_latency(test_results),
    ]

    loaded = []
    for name, data in [("test-results", test_results), ("manual-labels", manual_labels),
                       ("abstention-results", abstention_results),
                       ("hallucination-results", hallucination_results),
                       ("context-efficiency-results", context_eff),
                       ("ablation-results", ablation)]:
        loaded.append(f"  - {name}.csv: {'loaded' if data else 'not found'} "
                      f"({len(data)} rows)" if data else f"  - {name}.csv: not found")

    sections.append(f"\n---\n\n## Data Sources\n\n" + "\n".join(loaded))

    return "\n".join(sections)


if __name__ == "__main__":
    report = generate_report()
    out_path = DOCS_DIR / "evaluation-report.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")
    print(report)
    print(f"\nReport saved to {out_path}")
