"""
Phase 4.5 — Run All Evaluations

Master script that runs all Phase 4 evaluations in sequence:
  1. Abstention Rate (4.1)
  2. Hallucination Score (4.2)
  3. Context Efficiency (4.3)
  4. Ablation Studies (4.4)

Generates a combined evaluation report at docs/evaluation-report.md.

Usage:
    python -I eval_all.py
    python -I eval_all.py --skip ablation             # skip one phase
    python -I eval_all.py --skip efficiency --skip ablation
    python -I eval_all.py --delay 10
    python -I eval_all.py --dry-run
"""

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, ".")

from test_runner import BASE_URL, check_backend, check_documents

REPORT_MD = Path(__file__).parent / ".." / "docs" / "evaluation-report.md"

PHASES = {
    "abstention": {
        "title": "4.1 Abstention Rate",
        "module": "eval_abstention",
    },
    "hallucination": {
        "title": "4.2 Hallucination Score",
        "module": "eval_hallucination",
    },
    "efficiency": {
        "title": "4.3 Context Efficiency",
        "module": "eval_context_efficiency",
    },
    "ablation": {
        "title": "4.4 Ablation Studies",
        "module": "eval_ablation",
    },
}


def run_phase(name: str, phase: dict, delay: float, dry_run: bool) -> dict | None:
    """Import and run a single evaluation phase, return its summary."""
    print(f"\n{'#' * 60}")
    print(f"# {phase['title']}")
    print(f"{'#' * 60}\n")

    module = __import__(phase["module"])

    original_argv = sys.argv
    sys.argv = [phase["module"]]
    if dry_run:
        sys.argv.append("--dry-run")
    sys.argv.extend(["--delay", str(delay)])

    try:
        result = module.main()
        return result
    except SystemExit:
        return None
    finally:
        sys.argv = original_argv


def generate_combined_report(results: dict, documents: list, skipped: list):
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    doc_lines = "\n".join(f"  - `{d.get('doc_id', '?')}`: {d.get('chunks_count', '?')} chunks" for d in documents)

    report = f"""# FARE Evaluation Report

**Date:** {timestamp}
**System:** FARE (Faithful Abstaining RAG Evaluator)

## Documents Tested

{doc_lines}

## Executive Summary

"""

    abstention = results.get("abstention")
    hallucination = results.get("hallucination")

    if abstention:
        rate = abstention.get("abstention_rate", "N/A")
        status = "PASS" if isinstance(rate, (int, float)) and rate >= 90 else "FAIL"
        report += f"- **Abstention Rate:** {rate}% (target: >= 90%) — {status}\n"
    else:
        report += "- **Abstention Rate:** Not evaluated\n"

    if hallucination:
        score = hallucination.get("hallucination_score", "N/A")
        status = "PASS" if isinstance(score, (int, float)) and score >= 85 else "NEEDS REVIEW"
        report += f"- **Hallucination Score:** {score}% (target: >= 85%) — {status}\n"
    else:
        report += "- **Hallucination Score:** Not evaluated\n"

    efficiency_path = Path(__file__).parent / ".." / "docs" / "context-efficiency.md"
    if efficiency_path.exists():
        report += "- **Context Efficiency:** See [context-efficiency.md](context-efficiency.md)\n"
    else:
        report += "- **Context Efficiency:** Not evaluated\n"

    ablation_path = Path(__file__).parent / ".." / "docs" / "ablation-results.md"
    if ablation_path.exists():
        report += "- **Ablation Studies:** See [ablation-results.md](ablation-results.md)\n"
    else:
        report += "- **Ablation Studies:** Not evaluated\n"

    if skipped:
        report += f"\n*Skipped phases: {', '.join(skipped)}*\n"

    report += """
## Detailed Results

### Abstention Rate (Phase 4.1)

"""

    if abstention:
        report += f"""The system was tested on {abstention.get('total', 0)} queries where the answer was NOT in the document.

| Metric | Value |
|--------|-------|
| Total queries | {abstention.get('total', 0)} |
| Errors | {abstention.get('errors', 0)} |
| Correct refusals | {abstention.get('correct_refusals', 0)}/{abstention.get('evaluated', 0)} |
| **Abstention Rate** | **{abstention.get('abstention_rate', 0)}%** |

Full results: [abstention-results.csv](abstention-results.csv)
"""
    else:
        report += "Not evaluated (skipped or errored).\n"

    report += """
### Hallucination Score (Phase 4.2)

"""

    if hallucination:
        report += f"""The system was tested on {hallucination.get('total', 0)} queries where the answer WAS in the document.

| Metric | Value |
|--------|-------|
| Total queries | {hallucination.get('total', 0)} |
| Errors | {hallucination.get('errors', 0)} |
| Auto-faithful | {hallucination.get('faithful', 0)}/{hallucination.get('evaluated', 0)} |
| Auto-hallucinated | {hallucination.get('hallucinated', 0)}/{hallucination.get('evaluated', 0)} |
| Needs manual review | {hallucination.get('needs_review', 0)} |
| **Hallucination Score** | **{hallucination.get('hallucination_score', 0)}%** |

Full results: [hallucination-results.csv](hallucination-results.csv)
"""
    else:
        report += "Not evaluated (skipped or errored).\n"

    report += """
### Context Efficiency (Phase 4.3)

"""

    if efficiency_path.exists():
        report += "See [context-efficiency.md](context-efficiency.md) for the full K-value comparison.\n"
    else:
        report += "Not evaluated (skipped or errored).\n"

    report += """
### Ablation Studies (Phase 4.4)

"""

    if ablation_path.exists():
        report += "See [ablation-results.md](ablation-results.md) for the full method comparison.\n"
    else:
        report += "Not evaluated (skipped or errored).\n"

    report += """
## Limitations

- Hallucination detection is heuristic-based (keyword matching), not semantic
- Test document is small (5 pages, 5 chunks) — results may not generalize
- Gemini free tier limits throughput to 20 requests/day
- Manual review of flagged answers is recommended for publication-quality metrics

## Methodology

1. **Test Set:** 40 queries across 4 categories (factual, out-of-scope, multi-chunk, adversarial)
2. **Abstention Detection:** Pattern matching against known refusal phrases
3. **Hallucination Detection:** Extracting factual claims (numbers, proper nouns) and checking against source chunks
4. **Context Efficiency:** Varying K (chunks retrieved) and measuring tokens/accuracy trade-off
5. **Ablation:** Comparing hybrid (dense+BM25), dense-only, and BM25-only retrieval
"""

    with open(REPORT_MD, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\nCombined report written to: {REPORT_MD}")


def main():
    parser = argparse.ArgumentParser(description="FARE Full Evaluation Suite")
    parser.add_argument("--skip", action="append", default=[], help="Phase to skip (abstention, hallucination, efficiency, ablation)")
    parser.add_argument("--delay", type=float, default=5.0, help="Delay between queries (seconds)")
    parser.add_argument("--dry-run", action="store_true", help="Show plan without running")
    args = parser.parse_args()

    print("=" * 60)
    print("FARE Full Evaluation Suite (Phase 4)")
    print("=" * 60)

    if not check_backend():
        print(f"\nERROR: Backend not running at {BASE_URL}")
        sys.exit(1)

    docs = check_documents()
    if not docs:
        print("\nERROR: No documents ingested.")
        sys.exit(1)

    active = [name for name in PHASES if name not in args.skip]
    skipped = [name for name in PHASES if name in args.skip]

    print(f"Backend: OK | Documents: {len(docs)}")
    print(f"Phases: {', '.join(active)}")
    if skipped:
        print(f"Skipped: {', '.join(skipped)}")

    results = {}
    for i, name in enumerate(active):
        phase = PHASES[name]
        result = run_phase(name, phase, args.delay, args.dry_run)
        if result:
            results[name] = result

        if i < len(active) - 1 and not args.dry_run:
            wait = 30
            print(f"\nWaiting {wait}s before next phase...")
            time.sleep(wait)

    if not args.dry_run:
        generate_combined_report(results, docs, skipped)

    print("\n" + "=" * 60)
    print("EVALUATION COMPLETE")
    print("=" * 60)
    for name in PHASES:
        if name in results:
            r = results[name]
            if name == "abstention":
                print(f"  Abstention Rate:    {r.get('abstention_rate', 'N/A')}%")
            elif name == "hallucination":
                print(f"  Hallucination Score: {r.get('hallucination_score', 'N/A')}%")
            else:
                print(f"  {PHASES[name]['title']}: completed")
        elif name in skipped:
            print(f"  {PHASES[name]['title']}: skipped")
        else:
            print(f"  {PHASES[name]['title']}: not run")
    print("=" * 60)


if __name__ == "__main__":
    main()
