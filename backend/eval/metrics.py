import json
import logging
from pathlib import Path

logger = logging.getLogger("fare.eval.metrics")


def retrieval_precision_at_k(retrieved_ids: list[str], gold_ids: list[str], k: int) -> float:
    """Precision@k = |retrieved_top_k ∩ gold| / k"""
    if k <= 0:
        return 0.0
    top_k = retrieved_ids[:k]
    relevant = set(top_k) & set(gold_ids)
    return len(relevant) / k


def retrieval_recall_at_k(retrieved_ids: list[str], gold_ids: list[str], k: int) -> float:
    """Recall@k = |retrieved_top_k ∩ gold| / |gold|"""
    if not gold_ids:
        return 0.0
    top_k = retrieved_ids[:k]
    relevant = set(top_k) & set(gold_ids)
    return len(relevant) / len(gold_ids)


def compute_retrieval_metrics(run_id: str) -> dict:
    from eval.runner import RUNS_DIR, load_dataset

    run_dir = RUNS_DIR / run_id
    answers_path = run_dir / "answers.json"
    meta_path = run_dir / "run_meta.json"

    if not answers_path.exists():
        raise FileNotFoundError(f"No answers.json for run {run_id}")

    answers = json.loads(answers_path.read_text(encoding="utf-8"))
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    k = meta.get("k", 5)

    dataset = load_dataset()
    gold_map = {q.question_id: q.gold_chunk_ids for q in dataset
                if q.gold_chunk_ids}

    per_question = []
    precisions = []
    recalls = []

    for ans in answers:
        qid = ans["question_id"]
        gold_ids = gold_map.get(qid)
        if not gold_ids:
            continue

        retrieved_ids = ans.get("retrieved_chunk_ids", [])
        p = retrieval_precision_at_k(retrieved_ids, gold_ids, k)
        r = retrieval_recall_at_k(retrieved_ids, gold_ids, k)

        per_question.append({
            "question_id": qid,
            "question": ans.get("question", ""),
            "retrieved_ids": retrieved_ids[:k],
            "gold_ids": gold_ids,
            "precision_at_k": round(p, 4),
            "recall_at_k": round(r, 4),
            "k": k,
        })
        precisions.append(p)
        recalls.append(r)

    retrieval_path = run_dir / "retrieval_metrics.json"
    result = {
        "run_id": run_id,
        "k": k,
        "per_question": per_question,
    }
    with open(retrieval_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    n = len(precisions)
    return {
        "precision_at_k": round(sum(precisions) / n, 4) if n else None,
        "recall_at_k": round(sum(recalls) / n, 4) if n else None,
        "n": n,
        "k": k,
        "note": "Averaged over questions with at least one gold_chunk_id" if n else "No questions have gold_chunk_ids — populate the gold_chunk_ids column in the labeled dataset",
    }


# ---------------------------------------------------------------------------
# Accuracy, Refusal Precision, Refusal Recall
# ---------------------------------------------------------------------------

def compute_accuracy(run_id: str) -> dict:
    """Compute accuracy using human labels from human_verdicts.csv.

    Accuracy = (correct_answerable + correct_refusals) / total.
    A correct refusal on an unanswerable question counts as correct.
    """
    import csv
    from eval.runner import RUNS_DIR, load_dataset, EVAL_DIR

    run_dir = RUNS_DIR / run_id
    answers_path = run_dir / "answers.json"
    labels_path = EVAL_DIR / "labels" / "human_verdicts.csv"

    if not answers_path.exists():
        raise FileNotFoundError(f"No answers.json for run {run_id}")

    answers = json.loads(answers_path.read_text(encoding="utf-8"))
    dataset = load_dataset()
    answerable_map = {q.question_id: q.answerable for q in dataset}

    # Load human labels for this run
    human_labels = {}
    if labels_path.exists():
        with open(labels_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                aid = row.get("system_answer_id", "")
                if aid.startswith(run_id + "_"):
                    qid = row.get("question_id", "")
                    human_labels[qid] = row.get("correct", "").lower()

    correct_answerable = 0
    incorrect_answerable = 0
    correct_unanswerable = 0
    incorrect_unanswerable = 0
    unlabeled = 0

    for ans in answers:
        qid = ans["question_id"]
        is_answerable = answerable_map.get(qid, True)
        is_refusal = ans.get("is_refusal", False)

        human_correct = human_labels.get(qid)

        if is_answerable:
            if human_correct == "yes":
                correct_answerable += 1
            elif human_correct == "no":
                incorrect_answerable += 1
            else:
                unlabeled += 1
        else:
            # Unanswerable: correct if system refused
            if is_refusal:
                correct_unanswerable += 1
            else:
                incorrect_unanswerable += 1

    labeled_total = correct_answerable + incorrect_answerable + correct_unanswerable + incorrect_unanswerable
    total_correct = correct_answerable + correct_unanswerable

    return {
        "accuracy_overall": round(total_correct / labeled_total, 4) if labeled_total else None,
        "accuracy_answerable": round(correct_answerable / (correct_answerable + incorrect_answerable), 4)
            if (correct_answerable + incorrect_answerable) else None,
        "accuracy_unanswerable": round(correct_unanswerable / (correct_unanswerable + incorrect_unanswerable), 4)
            if (correct_unanswerable + incorrect_unanswerable) else None,
        "n_total": labeled_total,
        "n_labeled": labeled_total,
        "n_unlabeled": unlabeled,
        "correct_answerable": correct_answerable,
        "incorrect_answerable": incorrect_answerable,
        "correct_unanswerable": correct_unanswerable,
        "incorrect_unanswerable": incorrect_unanswerable,
        "note": "Unanswerable questions scored by refusal detection (no human label needed)"
            if not human_labels else None,
    }


def compute_refusal_metrics(run_id: str) -> dict:
    """Compute refusal precision, recall, and confusion matrix.

    Refusal Precision = correct_refusals / all_refusals
    Refusal Recall = correct_refusals / all_unanswerable
    """
    from eval.runner import RUNS_DIR, load_dataset

    run_dir = RUNS_DIR / run_id
    answers_path = run_dir / "answers.json"

    if not answers_path.exists():
        raise FileNotFoundError(f"No answers.json for run {run_id}")

    answers = json.loads(answers_path.read_text(encoding="utf-8"))
    dataset = load_dataset()
    answerable_map = {q.question_id: q.answerable for q in dataset}

    # Confusion matrix
    # TP: system refuses, question unanswerable (correct refusal)
    # FP: system refuses, question answerable (wrong refusal)
    # FN: system answers, question unanswerable (missed refusal)
    # TN: system answers, question answerable (correct answer attempt)
    tp = fp = fn = tn = 0

    per_question = []

    for ans in answers:
        qid = ans["question_id"]
        is_answerable = answerable_map.get(qid, True)
        is_refusal = ans.get("is_refusal", False)

        if is_refusal and not is_answerable:
            tp += 1
            label = "TP (correct refusal)"
        elif is_refusal and is_answerable:
            fp += 1
            label = "FP (wrong refusal)"
        elif not is_refusal and not is_answerable:
            fn += 1
            label = "FN (should have refused)"
        else:
            tn += 1
            label = "TN (answered, answerable)"

        per_question.append({
            "question_id": qid,
            "question": ans.get("question", ""),
            "answerable": is_answerable,
            "is_refusal": is_refusal,
            "label": label,
        })

    total_refusals = tp + fp
    total_unanswerable = tp + fn

    refusal_path = run_dir / "refusal_metrics.json"
    result_detail = {
        "run_id": run_id,
        "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "per_question": per_question,
    }
    with open(refusal_path, "w", encoding="utf-8") as f:
        json.dump(result_detail, f, indent=2)

    return {
        "refusal_precision": round(tp / total_refusals, 4) if total_refusals else None,
        "refusal_recall": round(tp / total_unanswerable, 4) if total_unanswerable else None,
        "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "n": len(answers),
        "total_refusals": total_refusals,
        "total_unanswerable": total_unanswerable,
    }


# ---------------------------------------------------------------------------
# Exact Match & Token F1
# ---------------------------------------------------------------------------

def compute_em_f1(run_id: str) -> dict:
    """Compute Exact Match and Token F1 for questions with gold_answer.

    EM is mainly meaningful for short factual questions.
    Token F1 is more forgiving of wording differences.
    """
    from eval.runner import RUNS_DIR, load_dataset
    from eval.normalize import exact_match, token_f1

    run_dir = RUNS_DIR / run_id
    answers_path = run_dir / "answers.json"

    if not answers_path.exists():
        raise FileNotFoundError(f"No answers.json for run {run_id}")

    answers = json.loads(answers_path.read_text(encoding="utf-8"))
    dataset = load_dataset()
    gold_map = {q.question_id: q.gold_answer for q in dataset if q.gold_answer}

    per_question = []
    em_scores = []
    f1_scores = []

    for ans in answers:
        qid = ans["question_id"]
        gold = gold_map.get(qid)
        if not gold:
            continue

        prediction = ans.get("answer_text", "")
        if ans.get("is_refusal"):
            prediction = ""

        em = exact_match(prediction, gold)
        f1 = token_f1(prediction, gold)

        per_question.append({
            "question_id": qid,
            "question": ans.get("question", ""),
            "prediction": prediction[:200],
            "gold": gold,
            "exact_match": em,
            "token_f1": round(f1, 4),
        })
        em_scores.append(em)
        f1_scores.append(f1)

    em_f1_path = run_dir / "em_f1_metrics.json"
    with open(em_f1_path, "w", encoding="utf-8") as f:
        json.dump({"run_id": run_id, "per_question": per_question}, f, indent=2)

    n = len(em_scores)
    return {
        "exact_match": round(sum(em_scores) / n, 4) if n else None,
        "token_f1": round(sum(f1_scores) / n, 4) if n else None,
        "n": n,
        "note": "EM is mainly meaningful for short factual questions" if n else "No questions have gold_answer",
    }


# ---------------------------------------------------------------------------
# Human-Agreement Accuracy + Cohen's Kappa
# ---------------------------------------------------------------------------

def cohens_kappa(labels_a: list[bool], labels_b: list[bool]) -> float:
    """Cohen's kappa for two binary label lists of equal length.

    kappa = (p_observed - p_expected) / (1 - p_expected)
    """
    if len(labels_a) != len(labels_b) or not labels_a:
        return 0.0

    n = len(labels_a)
    agree = sum(1 for a, b in zip(labels_a, labels_b) if a == b)
    p_observed = agree / n

    a_pos = sum(labels_a)
    b_pos = sum(labels_b)
    p_expected = ((a_pos * b_pos) + ((n - a_pos) * (n - b_pos))) / (n * n)

    if p_expected == 1.0:
        return 1.0 if p_observed == 1.0 else 0.0

    return (p_observed - p_expected) / (1 - p_expected)


def compute_human_agreement(run_id: str) -> dict:
    """Compare LLM judge verdicts with human labels.

    For each question where both judge and human verdicts exist, compares:
    - faithfulness (judge) vs faithful (human)
    - answer_relevance (judge) vs answer_relevant (human)

    Also computes inter-rater reliability (Cohen's kappa) between two human
    labelers if both are present.
    """
    import csv
    from eval.runner import RUNS_DIR, EVAL_DIR

    run_dir = RUNS_DIR / run_id
    claims_path = run_dir / "claims.json"
    relevance_path = run_dir / "relevance.json"
    labels_path = EVAL_DIR / "labels" / "human_verdicts.csv"

    if not labels_path.exists():
        return {"error": "No human_verdicts.csv found", "n": 0}

    # Load human labels grouped by (question_id, labeler)
    human = {}  # {question_id: {labeler: {faithful, answer_relevant, chunks}}}
    with open(labels_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            aid = row.get("system_answer_id", "")
            if not aid.startswith(run_id + "_"):
                continue
            qid = row.get("question_id", "")
            labeler = row.get("labeler", "unknown")
            if qid not in human:
                human[qid] = {}
            if labeler not in human[qid]:
                human[qid][labeler] = {
                    "faithful": None, "answer_relevant": None, "chunks": {}
                }
            faithful_val = row.get("faithful", "").lower()
            if faithful_val in ("yes", "no"):
                human[qid][labeler]["faithful"] = faithful_val == "yes"
            ar_val = row.get("answer_relevant", "").lower()
            if ar_val in ("yes", "no"):
                human[qid][labeler]["answer_relevant"] = ar_val == "yes"
            chunk_id = row.get("chunk_id", "")
            cr_val = row.get("chunk_relevant", "").lower()
            if chunk_id and cr_val in ("yes", "no"):
                human[qid][labeler]["chunks"][chunk_id] = cr_val == "yes"

    if not human:
        return {"error": f"No human labels found for run {run_id}", "n": 0}

    # Load judge verdicts
    judge_faithful = {}
    if claims_path.exists():
        claims_data = json.loads(claims_path.read_text(encoding="utf-8"))
        for item in claims_data.get("results", []):
            if item.get("faithfulness_score") is not None:
                judge_faithful[item["question_id"]] = item["faithfulness_score"] >= 0.5

    judge_answer_rel = {}
    judge_context_rel = {}
    if relevance_path.exists():
        rel_data = json.loads(relevance_path.read_text(encoding="utf-8"))
        for item in rel_data.get("answer_relevance", []):
            judge_answer_rel[item["question_id"]] = item.get("relevant", False)
        for item in rel_data.get("context_relevance", []):
            judge_context_rel[item["question_id"]] = {
                c["chunk_id"]: c["relevant"] for c in item.get("chunks", [])
            }

    # Compare judge vs each human labeler
    all_labelers = set()
    for qid_data in human.values():
        all_labelers.update(qid_data.keys())
    all_labelers = sorted(all_labelers)

    per_metric = {}
    disagreements = []

    for metric_name, judge_map, human_key in [
        ("faithfulness", judge_faithful, "faithful"),
        ("answer_relevance", judge_answer_rel, "answer_relevant"),
    ]:
        judge_labels = []
        human_labels_all = {lb: [] for lb in all_labelers}
        compared = 0
        matching = 0

        for qid in sorted(human.keys()):
            j_val = judge_map.get(qid)
            if j_val is None:
                continue
            for labeler in all_labelers:
                h_val = human.get(qid, {}).get(labeler, {}).get(human_key)
                if h_val is None:
                    continue
                compared += 1
                if j_val == h_val:
                    matching += 1
                else:
                    disagreements.append({
                        "metric": metric_name,
                        "question_id": qid,
                        "judge": j_val,
                        "human": h_val,
                        "labeler": labeler,
                    })
                judge_labels.append(j_val)
                human_labels_all[labeler].append(h_val)

        per_metric[metric_name] = {
            "agreement": round(matching / compared, 4) if compared else None,
            "n": compared,
        }

    # Inter-rater reliability between human labelers
    inter_rater = {}
    if len(all_labelers) >= 2:
        l1, l2 = all_labelers[0], all_labelers[1]
        for metric_name, human_key in [("faithfulness", "faithful"), ("answer_relevance", "answer_relevant")]:
            l1_labels = []
            l2_labels = []
            for qid in sorted(human.keys()):
                v1 = human.get(qid, {}).get(l1, {}).get(human_key)
                v2 = human.get(qid, {}).get(l2, {}).get(human_key)
                if v1 is not None and v2 is not None:
                    l1_labels.append(v1)
                    l2_labels.append(v2)
            if l1_labels:
                kappa = cohens_kappa(l1_labels, l2_labels)
                agree = sum(1 for a, b in zip(l1_labels, l2_labels) if a == b)
                inter_rater[metric_name] = {
                    "kappa": round(kappa, 4),
                    "agreement": round(agree / len(l1_labels), 4),
                    "n": len(l1_labels),
                    "labelers": [l1, l2],
                }

    # Overall agreement
    total_compared = sum(m["n"] for m in per_metric.values())
    total_matching = sum(int((m["agreement"] or 0) * m["n"]) for m in per_metric.values())
    overall_agreement = round(total_matching / total_compared, 4) if total_compared else None

    agreement_path = run_dir / "agreement_metrics.json"
    result_detail = {
        "run_id": run_id,
        "per_metric": per_metric,
        "inter_rater": inter_rater,
        "disagreements": disagreements,
        "labelers": all_labelers,
    }
    with open(agreement_path, "w", encoding="utf-8") as f:
        json.dump(result_detail, f, indent=2)

    return {
        "agreement_rate": overall_agreement,
        "n": total_compared,
        "per_metric": per_metric,
        "inter_rater": inter_rater,
        "disagreements": disagreements,
        "labelers": all_labelers,
    }
