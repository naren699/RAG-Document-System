import csv
import json
import logging
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from eval.schemas import TestQuestion, SystemAnswer, RunMetadata

logger = logging.getLogger("fare.eval")

EVAL_DIR = Path(__file__).parent.parent.parent / "data" / "eval"
RUNS_DIR = EVAL_DIR / "runs"
LABELED_CSV = Path(__file__).parent.parent.parent / "docs" / "test-queries-labeled.csv"

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
    "i couldn't find",
    "not in the uploaded documents",
]


def is_abstention(answer: str) -> bool:
    lower = answer.lower()
    return any(phrase in lower for phrase in ABSTAIN_PHRASES)


def load_dataset(path: Path | None = None) -> list[TestQuestion]:
    path = path or LABELED_CSV
    questions = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            gold_chunks = row.get("gold_chunk_ids", "")
            questions.append(TestQuestion(
                question_id=row["question_id"],
                question=row["question"],
                document_id=row.get("document_id", ""),
                gold_answer=row.get("gold_answer") or None,
                answerable=row.get("answerable", "yes").lower() == "yes",
                gold_chunk_ids=[c.strip() for c in gold_chunks.split("|") if c.strip()] if gold_chunks else [],
                answer_type=row.get("answer_type", "factual"),
                category=row.get("category", ""),
                expected_behavior=row.get("expected_behavior", ""),
            ))
    return questions


def _run_single_query(question: TestQuestion, k: int, method: str,
                      score_threshold: float | None) -> dict:
    from retriever import retrieve_hybrid, retrieve_dense_only, retrieve_bm25_only
    from llm_provider import generate_answer, get_llm_provider, get_model_name
    from grounding import compute_grounding_score

    start = time.time()

    if method == "hybrid":
        chunks, timings = retrieve_hybrid(question.question, k=k,
                                          doc_id=None, score_threshold=score_threshold)
    elif method == "dense":
        chunks, timings = retrieve_dense_only(question.question, k=k,
                                              doc_id=None, score_threshold=score_threshold)
    elif method == "bm25":
        chunks, timings = retrieve_bm25_only(question.question, k=k,
                                             doc_id=None, score_threshold=score_threshold)
    else:
        raise ValueError(f"Unknown retrieval method: {method}")

    if not chunks:
        latency_ms = int((time.time() - start) * 1000)
        return {
            "answer_text": "I couldn't find this in the uploaded documents.",
            "is_refusal": True,
            "retrieved_chunk_ids": [],
            "retrieved_chunks": [],
            "latency_ms": latency_ms,
            "tokens_used": {"input_tokens": 0, "output_tokens": 0},
            "grounding": {"score": 0.0, "grounded_claims": 0, "total_claims": 0, "claims": []},
            "model": "none",
            "provider": "none",
        }

    result = generate_answer(question.question, chunks)
    latency_ms = int((time.time() - start) * 1000)
    answer_text = result.get("answer", "")
    grounding = compute_grounding_score(answer_text, chunks)

    return {
        "answer_text": answer_text,
        "is_refusal": is_abstention(answer_text) or not chunks,
        "retrieved_chunk_ids": [c.get("chunk_id", "") for c in chunks],
        "retrieved_chunks": [
            {"chunk_id": c.get("chunk_id", ""), "text": c.get("text", "")[:500],
             "score": c.get("score", 0), "source": c.get("source", ""),
             "page_num": c.get("page_num")}
            for c in chunks
        ],
        "latency_ms": latency_ms,
        "tokens_used": {
            "input_tokens": result.get("input_tokens", 0),
            "output_tokens": result.get("output_tokens", 0),
        },
        "grounding": grounding,
        "model": result.get("model", "unknown"),
        "provider": result.get("provider", "unknown"),
    }


def _execute_run(run_id: str, run_dir: Path, dataset: list[TestQuestion],
                 k: int, method: str, score_threshold: float | None):
    meta_path = run_dir / "run_meta.json"
    answers_path = run_dir / "answers.json"
    answers = []

    try:
        for i, q in enumerate(dataset):
            logger.info(f"Run {run_id}: query {i+1}/{len(dataset)} — {q.question[:60]}")
            result = _run_single_query(q, k, method, score_threshold)

            answer = SystemAnswer(
                answer_id=f"{run_id}_{q.question_id}",
                run_id=run_id,
                question_id=q.question_id,
                question=q.question,
                **result,
            )
            answers.append(answer.model_dump())

            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            meta["completed_questions"] = i + 1
            meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

        with open(answers_path, "w", encoding="utf-8") as f:
            json.dump(answers, f, indent=2, default=str)

        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["status"] = "completed"
        meta["completed_questions"] = len(dataset)
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        logger.info(f"Run {run_id} completed: {len(answers)} answers")

    except Exception as e:
        logger.error(f"Run {run_id} failed: {e}")
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["status"] = "failed"
        meta["error"] = str(e)
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")


def start_eval_run(k: int = 5, method: str = "hybrid",
                   score_threshold: float | None = None,
                   dataset_path: Path | None = None) -> RunMetadata:
    from llm_provider import get_llm_provider, get_model_name

    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    dataset = load_dataset(dataset_path)

    meta = RunMetadata(
        run_id=run_id,
        status="running",
        timestamp=datetime.now(timezone.utc).isoformat(),
        model=get_model_name(),
        provider=get_llm_provider(),
        retrieval_method=method,
        k=k,
        score_threshold=score_threshold,
        dataset=str(dataset_path or LABELED_CSV),
        total_questions=len(dataset),
        completed_questions=0,
    )

    meta_path = run_dir / "run_meta.json"
    meta_path.write_text(json.dumps(meta.model_dump(), indent=2), encoding="utf-8")

    thread = threading.Thread(
        target=_execute_run,
        args=(run_id, run_dir, dataset, k, method, score_threshold),
        daemon=True,
    )
    thread.start()

    return meta


def list_runs() -> list[dict]:
    runs = []
    if not RUNS_DIR.exists():
        return runs
    for run_dir in sorted(RUNS_DIR.iterdir(), reverse=True):
        meta_path = run_dir / "run_meta.json"
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            runs.append(meta)
    return runs


def get_run(run_id: str) -> dict | None:
    run_dir = RUNS_DIR / run_id
    meta_path = run_dir / "run_meta.json"
    if not meta_path.exists():
        return None

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    answers_path = run_dir / "answers.json"
    if answers_path.exists():
        meta["answers"] = json.loads(answers_path.read_text(encoding="utf-8"))
    return meta


def validate_dataset(path: Path | None = None) -> dict:
    dataset = load_dataset(path)
    errors = []
    for q in dataset:
        if not q.question_id:
            errors.append(f"Missing question_id for question: {q.question[:50]}")
        if not q.question:
            errors.append(f"Empty question for id: {q.question_id}")
        if not q.document_id:
            errors.append(f"Missing document_id for id: {q.question_id}")
        if q.answerable and not q.gold_answer:
            errors.append(f"Answerable question {q.question_id} has no gold_answer")
        if q.answer_type not in ("factual", "multi-part", "entity-trap", "Tanglish", "refusal"):
            errors.append(f"Invalid answer_type '{q.answer_type}' for id: {q.question_id}")

    return {
        "total_questions": len(dataset),
        "answerable": sum(1 for q in dataset if q.answerable),
        "unanswerable": sum(1 for q in dataset if not q.answerable),
        "answer_types": {t: sum(1 for q in dataset if q.answer_type == t)
                         for t in sorted(set(q.answer_type for q in dataset))},
        "with_gold_chunks": sum(1 for q in dataset if q.gold_chunk_ids),
        "with_gold_answer": sum(1 for q in dataset if q.gold_answer),
        "errors": errors,
        "valid": len(errors) == 0,
    }
