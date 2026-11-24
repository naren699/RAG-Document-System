import csv
import io
import json
import logging
from pathlib import Path

logger = logging.getLogger("fare.eval.export")


def _load_targets() -> dict:
    targets_path = Path(__file__).parent.parent.parent / "config" / "eval_targets.json"
    if targets_path.exists():
        data = json.loads(targets_path.read_text(encoding="utf-8"))
        return data.get("metrics", {})
    return {}


def aggregate_metrics(run_id: str) -> dict:
    """Aggregate all computed metrics for a run into a single response.

    Each metric includes: name, target, measured, n, ci_95, meets_target, data_source.
    Metrics without results show measured=None ("Not measured yet").
    """
    from eval.runner import RUNS_DIR
    from eval.confidence import wilson_ci

    run_dir = RUNS_DIR / run_id
    targets = _load_targets()

    def _metric(key: str, name: str, measured: float | None, n: int,
                successes: int | None = None, data_source: str = "",
                ci_total: int | None = None):
        t = targets.get(key, {})
        target_val = t.get("target")
        ci = None
        ci_denom = ci_total if ci_total is not None else n
        if successes is not None and ci_denom > 0 and successes <= ci_denom:
            lo, hi = wilson_ci(successes, ci_denom)
            ci = [round(lo, 4), round(hi, 4)]

        meets_target = None
        if measured is not None and target_val is not None:
            meets_target = measured >= target_val

        return {
            "key": key,
            "name": name,
            "target": target_val,
            "target_display": t.get("display", ""),
            "measured": measured,
            "n": n,
            "ci_95": ci,
            "meets_target": meets_target,
            "data_source": data_source,
        }

    metrics = []

    # Accuracy (from refusal_metrics + human labels)
    refusal_path = run_dir / "refusal_metrics.json"
    accuracy_measured = None
    accuracy_n = 0
    accuracy_correct = 0
    if refusal_path.exists():
        ref = json.loads(refusal_path.read_text(encoding="utf-8"))
        cm = ref.get("confusion", {})
        accuracy_n = cm.get("tp", 0) + cm.get("fp", 0) + cm.get("fn", 0) + cm.get("tn", 0)
        accuracy_correct = cm.get("tp", 0) + cm.get("tn", 0)
        accuracy_measured = round(accuracy_correct / accuracy_n, 4) if accuracy_n else None
    metrics.append(_metric("accuracy", "Accuracy", accuracy_measured, accuracy_n,
                           accuracy_correct if accuracy_n else None, "human_labels + refusal_detection"))

    # Faithfulness
    claims_path = run_dir / "claims.json"
    faith_measured = None
    faith_n = 0
    faith_supported = 0
    faith_total_claims = 0
    if claims_path.exists():
        cd = json.loads(claims_path.read_text(encoding="utf-8"))
        scores = [r["faithfulness_score"] for r in cd.get("results", [])
                  if r.get("faithfulness_score") is not None]
        faith_n = len(scores)
        if scores:
            faith_measured = round(sum(scores) / len(scores), 4)
        for r in cd.get("results", []):
            for c in r.get("claims", []):
                faith_total_claims += 1
                if c.get("supported"):
                    faith_supported += 1
    metrics.append(_metric("faithfulness", "Faithfulness", faith_measured, faith_n,
                           faith_supported if faith_total_claims else None, "llm_judge",
                           ci_total=faith_total_claims))

    # Answer Relevance
    rel_path = run_dir / "relevance.json"
    ar_measured = None
    ar_n = 0
    ar_relevant = 0
    cr_measured = None
    cr_n = 0
    cr_relevant = 0
    cr_total = 0
    if rel_path.exists():
        rd = json.loads(rel_path.read_text(encoding="utf-8"))
        ar_items = rd.get("answer_relevance", [])
        ar_n = len(ar_items)
        ar_relevant = sum(1 for i in ar_items if i.get("relevant"))
        ar_measured = round(ar_relevant / ar_n, 4) if ar_n else None

        cr_items = rd.get("context_relevance", [])
        for item in cr_items:
            for ch in item.get("chunks", []):
                cr_total += 1
                if ch.get("relevant"):
                    cr_relevant += 1
        cr_scores = [item["context_relevance"] for item in cr_items if item.get("chunks")]
        cr_n = len(cr_scores)
        cr_measured = round(sum(cr_scores) / len(cr_scores), 4) if cr_scores else None

    metrics.append(_metric("answer_relevance", "Answer Relevance", ar_measured, ar_n,
                           ar_relevant if ar_n else None, "llm_judge"))
    metrics.append(_metric("context_relevance", "Context Relevance", cr_measured, cr_n,
                           cr_relevant if cr_total else None, "llm_judge"))

    # Human-Agreement Accuracy
    agree_path = run_dir / "agreement_metrics.json"
    ha_measured = None
    ha_n = 0
    if agree_path.exists():
        ad = json.loads(agree_path.read_text(encoding="utf-8"))
        ha_n = sum(m["n"] for m in ad.get("per_metric", {}).values())
        ha_matching = sum(int((m.get("agreement") or 0) * m["n"])
                         for m in ad.get("per_metric", {}).values())
        ha_measured = round(ha_matching / ha_n, 4) if ha_n else None
    metrics.append(_metric("human_agreement_accuracy", "Human-Agreement Accuracy",
                           ha_measured, ha_n, None, "human_labels"))

    # Retrieval Precision@k and Recall@k
    ret_path = run_dir / "retrieval_metrics.json"
    rp_measured = None
    rr_measured = None
    ret_n = 0
    if ret_path.exists():
        rtd = json.loads(ret_path.read_text(encoding="utf-8"))
        pq = rtd.get("per_question", [])
        ret_n = len(pq)
        if pq:
            rp_measured = round(sum(q["precision_at_k"] for q in pq) / len(pq), 4)
            rr_measured = round(sum(q["recall_at_k"] for q in pq) / len(pq), 4)
    metrics.append(_metric("retrieval_precision_at_k", "Retrieval Precision@k",
                           rp_measured, ret_n, None, "gold_data"))
    metrics.append(_metric("retrieval_recall_at_k", "Retrieval Recall@k",
                           rr_measured, ret_n, None, "gold_data"))

    # Refusal Precision and Recall
    rp_val = None
    rr_val = None
    ref_n = 0
    ref_tp = 0
    ref_total_refusals = 0
    ref_total_unanswerable = 0
    if refusal_path.exists():
        ref = json.loads(refusal_path.read_text(encoding="utf-8"))
        cm = ref.get("confusion", {})
        ref_tp = cm.get("tp", 0)
        ref_total_refusals = ref_tp + cm.get("fp", 0)
        ref_total_unanswerable = ref_tp + cm.get("fn", 0)
        ref_n = cm.get("tp", 0) + cm.get("fp", 0) + cm.get("fn", 0) + cm.get("tn", 0)
        rp_val = round(ref_tp / ref_total_refusals, 4) if ref_total_refusals else None
        rr_val = round(ref_tp / ref_total_unanswerable, 4) if ref_total_unanswerable else None
    metrics.append(_metric("refusal_precision", "Refusal Precision", rp_val,
                           ref_total_refusals,
                           ref_tp if ref_total_refusals else None, "gold_data"))
    metrics.append(_metric("refusal_recall", "Refusal Recall", rr_val,
                           ref_total_unanswerable,
                           ref_tp if ref_total_unanswerable else None, "gold_data"))

    # Token F1 + Exact Match
    emf1_path = run_dir / "em_f1_metrics.json"
    f1_measured = None
    em_measured = None
    emf1_n = 0
    if emf1_path.exists():
        ed = json.loads(emf1_path.read_text(encoding="utf-8"))
        pq = ed.get("per_question", [])
        emf1_n = len(pq)
        if pq:
            f1_measured = round(sum(q["token_f1"] for q in pq) / len(pq), 4)
            em_measured = round(sum(q["exact_match"] for q in pq) / len(pq), 4)
    metrics.append(_metric("token_f1", "Token F1", f1_measured, emf1_n, None, "gold_data"))
    metrics.append(_metric("exact_match", "Exact Match", em_measured, emf1_n, None, "gold_data"))

    # Confusion matrix for refusals
    confusion = None
    if refusal_path.exists():
        ref = json.loads(refusal_path.read_text(encoding="utf-8"))
        confusion = ref.get("confusion")

    return {
        "run_id": run_id,
        "metrics": metrics,
        "confusion": confusion,
    }


def export_csv(run_id: str) -> str:
    """Generate CSV string with all metrics for a run."""
    data = aggregate_metrics(run_id)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["metric", "target", "measured", "n", "ci_95_lower", "ci_95_upper",
                     "meets_target", "data_source"])
    for m in data["metrics"]:
        ci = m.get("ci_95") or [None, None]
        writer.writerow([
            m["name"],
            m["target"],
            m["measured"],
            m["n"],
            ci[0],
            ci[1],
            m["meets_target"],
            m["data_source"],
        ])
    return output.getvalue()


def export_json(run_id: str) -> dict:
    """Generate full JSON export for a run."""
    return aggregate_metrics(run_id)


def generate_report(run_id: str) -> dict:
    """Generate the final evaluation report with all metrics, targets, and analysis."""
    from eval.runner import RUNS_DIR
    from datetime import datetime, timezone

    run_dir = RUNS_DIR / run_id
    meta_path = run_dir / "run_meta.json"

    if not meta_path.exists():
        raise FileNotFoundError(f"No run_meta.json for run {run_id}")

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    targets_data = _load_targets()
    agg = aggregate_metrics(run_id)

    misses = []
    for m in agg["metrics"]:
        if m["meets_target"] is False:
            gap = None
            if m["target"] is not None and m["measured"] is not None:
                gap = round(m["target"] - m["measured"], 4)
            misses.append({
                "metric": m["name"],
                "target": m["target"],
                "measured": m["measured"],
                "gap": gap,
            })

    automatic_metrics = [m["name"] for m in agg["metrics"]
                         if m["data_source"] == "llm_judge"]
    human_label_metrics = [m["name"] for m in agg["metrics"]
                           if m["data_source"] in ("human_labels", "human_labels + refusal_detection")]
    gold_data_metrics = [m["name"] for m in agg["metrics"]
                         if m["data_source"] == "gold_data"]

    not_computed = [m["name"] for m in agg["metrics"] if m["measured"] is None]

    return {
        "report_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "run_id": run_id,
        "system": {
            "model": meta.get("model", "unknown"),
            "provider": meta.get("provider", "unknown"),
            "retrieval_method": meta.get("retrieval_method", "hybrid"),
            "k": meta.get("k", 5),
            "total_questions": meta.get("total_questions", 0),
        },
        "metrics": agg["metrics"],
        "confusion": agg.get("confusion"),
        "metrics_missing_targets": misses,
        "metrics_by_type": {
            "automatic_llm_judge": automatic_metrics,
            "human_labeled": human_label_metrics,
            "gold_data": gold_data_metrics,
        },
        "not_computed": not_computed,
        "not_computed_reasons": {
            name: "No labels or gold data available for this metric"
            for name in not_computed
        },
    }
