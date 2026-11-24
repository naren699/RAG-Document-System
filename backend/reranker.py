import logging
import math
import time

from sentence_transformers import CrossEncoder

logger = logging.getLogger(__name__)

RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
_model = None


def _get_model() -> CrossEncoder:
    global _model
    if _model is None:
        logger.info(f"Loading reranker model: {RERANKER_MODEL}")
        start = time.time()
        _model = CrossEncoder(RERANKER_MODEL)
        elapsed = int((time.time() - start) * 1000)
        logger.info(f"Reranker model loaded in {elapsed}ms")
    return _model


def rerank(
    query: str,
    chunks: list[dict],
    top_k: int = 5,
    score_threshold: float | None = None,
) -> tuple[list[dict], int, int]:
    """Rerank chunks using a cross-encoder, optionally filtering by score threshold.

    Returns (reranked_chunks, elapsed_ms, total_candidates).
    """
    if not chunks:
        return [], 0, {"scored": 0, "passed_threshold": 0, "selected": 0}

    start = time.time()
    model = _get_model()
    pairs = [[query, c["text"]] for c in chunks]

    scores = model.predict(
        pairs,
        show_progress_bar=False,
    )
    elapsed_ms = int((time.time() - start) * 1000)

    SIGMOID_TEMPERATURE = 4.0
    for i, chunk in enumerate(chunks):
        raw = float(scores[i])
        scaled = raw / SIGMOID_TEMPERATURE
        if scaled < -500:
            normalized = 0.0
        elif scaled > 500:
            normalized = 1.0
        else:
            normalized = 1.0 / (1.0 + math.exp(-scaled))
        chunk["rerank_score_raw"] = round(raw, 4)
        chunk["rerank_score"] = normalized

    chunks.sort(key=lambda c: c["rerank_score"], reverse=True)

    decisions = []
    if score_threshold is not None:
        filtered = [c for c in chunks if c["rerank_score"] >= score_threshold]
    else:
        filtered = chunks

    sent = filtered[:top_k]
    sent_ids = {c.get("chunk_id") for c in sent}

    for rank, c in enumerate(chunks):
        cid = c.get("chunk_id", "?")
        score = c["rerank_score"]
        passed = score >= score_threshold if score_threshold is not None else True

        if not passed:
            decision = "dropped"
            reason = f"below threshold ({score:.4f} < {score_threshold})"
        elif cid not in sent_ids:
            decision = "dropped"
            reason = f"outside top-{top_k}"
        else:
            decision = "sent"
            reason = ""

        decisions.append({
            "chunk_id": cid,
            "rank": rank + 1,
            "rerank_score": round(score, 6),
            "rerank_score_raw": c.get("rerank_score_raw"),
            "passed_threshold": passed,
            "sent_to_model": cid in sent_ids,
            "decision": decision,
            "drop_reason": reason,
        })

    if any(d["decision"] == "dropped" for d in decisions):
        log_lines = [f"  {d['decision'].upper()} {d['chunk_id']}: {d['rerank_score']:.4f} — {d['drop_reason']}"
                     for d in decisions if d["decision"] == "dropped"]
        logger.info("Rerank decisions:\n" + "\n".join(log_lines))

    counts = {
        "scored": len(chunks),
        "passed_threshold": len(filtered),
        "selected": len(sent),
    }
    logger.info(
        f"Reranked {counts['scored']} chunks in {elapsed_ms}ms: "
        f"{counts['passed_threshold']} passed, {counts['selected']} selected "
        f"(scores: {[round(c['rerank_score'], 4) for c in chunks[:5]]})"
        + (f" (threshold {score_threshold})" if score_threshold is not None else "")
    )
    return sent, elapsed_ms, counts, decisions
