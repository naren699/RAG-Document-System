import logging
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
    score_threshold: float = 0.1,
) -> tuple[list[dict], int, int]:
    """Rerank chunks using a cross-encoder and filter by score threshold.

    Returns (filtered_chunks, elapsed_ms, total_candidates).
    """
    if not chunks:
        return [], 0, 0

    model = _get_model()
    pairs = [[query, c["text"]] for c in chunks]

    start = time.time()
    scores = model.predict(
        pairs,
        show_progress_bar=False,
    )
    elapsed_ms = int((time.time() - start) * 1000)

    for i, chunk in enumerate(chunks):
        raw = float(scores[i])
        chunk["rerank_score_raw"] = round(raw, 4)
        chunk["rerank_score"] = round(raw, 4)

    chunks.sort(key=lambda c: c["rerank_score"], reverse=True)

    filtered = [c for c in chunks if c["rerank_score"] >= score_threshold]
    result = filtered[:top_k]

    logger.info(
        f"Reranked {len(chunks)} chunks in {elapsed_ms}ms: "
        f"{len(filtered)} above threshold {score_threshold}, returning {len(result)}"
    )
    return result, elapsed_ms, len(chunks)
