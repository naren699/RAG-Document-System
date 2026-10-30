"""Evaluate page classifier against hand-labeled ground truth."""

import csv
import sys
from collections import defaultdict
from pathlib import Path

from page_classifier import classify_pages

DEFAULT_GT_PATH = Path(__file__).parent / "tests" / "classifier_ground_truth.csv"
OUTPUT_DIR = Path(__file__).parent.parent / "docs"


def load_ground_truth(gt_path: Path) -> list[dict]:
    rows = []
    with open(gt_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append({
                "pdf_file": row["pdf_file"].strip(),
                "page_num": int(row["page_num"]),
                "expected_type": row["expected_type"].strip(),
                "notes": row.get("notes", "").strip(),
            })
    return rows


def run_classifier(gt_rows: list[dict]) -> list[dict]:
    by_pdf = defaultdict(list)
    for row in gt_rows:
        by_pdf[row["pdf_file"]].append(row)

    predictions = {}
    for pdf_file in by_pdf:
        pdf_path = Path(__file__).parent.parent / "data" / pdf_file
        if not pdf_path.exists():
            print(f"WARNING: PDF not found: {pdf_path}")
            continue
        for page_info in classify_pages(str(pdf_path)):
            predictions[(pdf_file, page_info["page_num"])] = page_info

    results = []
    for row in gt_rows:
        key = (row["pdf_file"], row["page_num"])
        pred = predictions.get(key)
        if pred is None:
            results.append({**row, "predicted": "MISSING", "match": False,
                            "visual_ratio": None, "text_length": None})
        else:
            match = pred["page_type"] == row["expected_type"]
            results.append({**row, "predicted": pred["page_type"], "match": match,
                            "visual_ratio": pred["visual_ratio"],
                            "text_length": pred["text_length"]})
    return results


def print_report(results: list[dict]) -> None:
    header = f"{'PDF':<30} | {'Page':>4} | {'Expected':<10} | {'Predicted':<10} | {'Match':<5} | {'vis_ratio':>9} | {'text_len':>8}"
    print(header)
    print("-" * len(header))
    for r in results:
        vr = f"{r['visual_ratio']:.3f}" if r["visual_ratio"] is not None else "N/A"
        tl = str(r["text_length"]) if r["text_length"] is not None else "N/A"
        tag = "YES" if r["match"] else "NO"
        print(f"{r['pdf_file']:<30} | {r['page_num']:>4} | {r['expected_type']:<10} | {r['predicted']:<10} | {tag:<5} | {vr:>9} | {tl:>8}")

    total = len(results)
    correct = sum(1 for r in results if r["match"])
    pct = (correct / total * 100) if total else 0
    print(f"\nAccuracy: {correct}/{total} = {pct:.1f}%")

    misses = [r for r in results if not r["match"]]
    if misses:
        print(f"\nMisclassified ({len(misses)}):")
        for r in misses:
            vr = f"{r['visual_ratio']:.3f}" if r["visual_ratio"] is not None else "N/A"
            tl = str(r["text_length"]) if r["text_length"] is not None else "N/A"
            print(f"  {r['pdf_file']} p{r['page_num']}: expected={r['expected_type']} got={r['predicted']}  "
                  f"visual_ratio={vr} text_len={tl}")


def save_csv(results: list[dict], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "pdf_file", "page_num", "expected_type", "predicted", "match",
            "visual_ratio", "text_length", "notes",
        ])
        writer.writeheader()
        writer.writerows(results)
    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    gt_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_GT_PATH
    if not gt_path.exists():
        print(f"Ground truth file not found: {gt_path}")
        sys.exit(1)

    gt_rows = load_ground_truth(gt_path)
    print(f"Loaded {len(gt_rows)} labeled pages from {gt_path}\n")

    results = run_classifier(gt_rows)
    print_report(results)
    save_csv(results, OUTPUT_DIR / "classifier-results.csv")
