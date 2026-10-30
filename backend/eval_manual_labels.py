"""Interactive manual labeling of test results for evaluation."""

import csv
import sys
from pathlib import Path

DEFAULT_RESULTS_PATH = Path(__file__).parent.parent / "docs" / "test-results.csv"
LABELS_PATH = Path(__file__).parent.parent / "docs" / "manual-labels.csv"

VALID_LABELS = [
    "correct",
    "faithful_but_wrong",
    "hallucinated",
    "correct_refusal",
    "wrong_refusal",
]


def load_existing_labels(labels_path: Path) -> dict[str, dict]:
    labeled = {}
    if not labels_path.exists():
        return labeled
    with open(labels_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            labeled[row["query_id"]] = row
    return labeled


def load_results(results_path: Path) -> list[dict]:
    rows = []
    with open(results_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append(row)
    return rows


def save_labels(labels: dict[str, dict], labels_path: Path) -> None:
    labels_path.parent.mkdir(parents=True, exist_ok=True)
    sorted_labels = sorted(labels.values(), key=lambda r: int(r.get("query_id", 0)))
    with open(labels_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["query_id", "query", "label", "notes"])
        writer.writeheader()
        writer.writerows(sorted_labels)


def truncate(text: str, max_len: int = 500) -> str:
    if not text or len(text) <= max_len:
        return text or ""
    return text[:max_len] + "..."


def label_results(results_path: Path, labels_path: Path) -> None:
    results = load_results(results_path)
    existing = load_existing_labels(labels_path)

    unlabeled = [r for r in results if r.get("query_id", "") not in existing]
    total = len(results)
    already = len(existing)

    if not unlabeled:
        print(f"All {total} queries already labeled. Nothing to do.")
        return

    print(f"\n{total} total queries, {already} already labeled, {len(unlabeled)} remaining.")
    print(f"Valid labels: {', '.join(VALID_LABELS)}")
    print("Enter 's' to skip, 'q' to quit and save.\n")

    labels = dict(existing)
    labeled_this_session = 0

    for i, row in enumerate(unlabeled, 1):
        qid = row.get("query_id", "?")
        query = row.get("query", "")
        answer = row.get("answer", "")
        sources = row.get("sources", row.get("num_sources", ""))

        print(f"--- [{i}/{len(unlabeled)}] Query ID: {qid} ---")
        print(f"  Q: {query}")
        print(f"  A: {truncate(answer)}")
        if sources:
            print(f"  Sources: {truncate(str(sources), 200)}")

        while True:
            choice = input(f"  Label [{'/'.join(VALID_LABELS)}/s/q]: ").strip().lower()
            if choice == "q":
                save_labels(labels, labels_path)
                print(f"\nSaved {labeled_this_session} new labels (total: {len(labels)}).")
                return
            if choice == "s":
                print("  Skipped.")
                break
            if choice in VALID_LABELS:
                notes = input("  Notes (optional): ").strip()
                labels[qid] = {
                    "query_id": qid,
                    "query": query,
                    "label": choice,
                    "notes": notes,
                }
                labeled_this_session += 1
                print(f"  -> {choice}")
                break
            print(f"  Invalid. Choose from: {', '.join(VALID_LABELS)}, s, q")

    save_labels(labels, labels_path)
    print(f"\nDone. Labeled {labeled_this_session} new queries (total: {len(labels)}).")
    print(f"Labels saved to {labels_path}")


if __name__ == "__main__":
    results_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_RESULTS_PATH
    if not results_path.exists():
        print(f"Results file not found: {results_path}")
        print("Run test_runner.py first to generate test results.")
        sys.exit(1)

    label_results(results_path, LABELS_PATH)
