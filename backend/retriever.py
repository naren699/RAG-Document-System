import logging
import os
import time

from embedder import embed_query
from vector_store import query_dense, query_visual
from bm25_retriever import query_bm25

logger = logging.getLogger(__name__)

COLPALI_ENABLED = os.getenv("COLPALI_ENABLED", "false").lower() == "true"
DEFAULT_K = 5
DEFAULT_SCORE_THRESHOLD: float | None = None
_env_threshold = os.getenv("SCORE_THRESHOLD")
if _env_threshold is not None:
    DEFAULT_SCORE_THRESHOLD = float(_env_threshold)


def _retrieve_visual(query: str, k: int = 2, doc_id: str | None = None) -> list[dict]:
    if not COLPALI_ENABLED:
        return []
    try:
        from colpali_processor import embed_query_colpali
        start = time.time()
        q_emb = embed_query_colpali(query)
        results = query_visual(q_emb, k=k, doc_id=doc_id)
        elapsed = int((time.time() - start) * 1000)
        logger.info(f"Visual retrieval: {len(results)} results in {elapsed}ms")
        return results
    except Exception as e:
        logger.warning(f"Visual retrieval failed: {e}")
        return []


def retrieve_hybrid(query: str, k: int = DEFAULT_K, doc_id: str | None = None,
                    score_threshold: float | None = DEFAULT_SCORE_THRESHOLD) -> tuple[list[dict], dict]:
    """Hybrid retrieval: dense + BM25 via RRF, then cross-encoder reranking.

    Returns (chunks, timings_dict).
    """
    from reranker import rerank

    timings = {}

    start = time.time()
    query_embedding = embed_query(query)
    timings["embed_query_ms"] = int((time.time() - start) * 1000)

    start = time.time()
    dense_results = query_dense(query_embedding, k=k * 2, doc_id=doc_id)
    timings["dense_search_ms"] = int((time.time() - start) * 1000)

    start = time.time()
    bm25_results = query_bm25(query, k=k * 2, doc_id=doc_id)
    timings["bm25_search_ms"] = int((time.time() - start) * 1000)

    rrf_scores = {}
    chunk_data = {}
    rrf_k = 60

    for rank, chunk in enumerate(dense_results):
        cid = chunk["chunk_id"]
        rrf_scores[cid] = rrf_scores.get(cid, 0) + 1 / (rrf_k + rank + 1)
        chunk_data[cid] = chunk
        chunk_data[cid]["dense_score"] = chunk.get("score", 0)
        chunk_data[cid]["dense_rank"] = rank + 1

    for rank, chunk in enumerate(bm25_results):
        cid = chunk["chunk_id"]
        rrf_scores[cid] = rrf_scores.get(cid, 0) + 1 / (rrf_k + rank + 1)
        if cid not in chunk_data:
            chunk_data[cid] = chunk
        chunk_data[cid]["bm25_score"] = chunk.get("score", 0)
        chunk_data[cid]["bm25_rank"] = rank + 1

    sorted_ids = sorted(rrf_scores, key=lambda x: rrf_scores[x], reverse=True)

    candidates = []
    for cid in sorted_ids[:k * 2]:
        chunk = chunk_data[cid]
        chunk["rrf_score"] = round(rrf_scores[cid], 6)
        candidates.append(chunk)

    reranked, rerank_ms, candidates_total = rerank(query, candidates, top_k=k, score_threshold=score_threshold)
    timings["rerank_ms"] = rerank_ms
    timings["candidates_total"] = candidates_total
    timings["candidates_kept"] = len(reranked)

    for chunk in reranked:
        chunk["score"] = chunk["rerank_score"]

    visual_results = _retrieve_visual(query, k=2, doc_id=doc_id)
    if visual_results:
        existing_ids = {c["chunk_id"] for c in reranked}
        for vc in visual_results:
            if vc["chunk_id"] not in existing_ids and len(reranked) < k + 2:
                reranked.append(vc)

    logger.info(
        f"Hybrid retrieval for '{query[:50]}...': "
        f"{len(dense_results)} dense, {len(bm25_results)} BM25, "
        f"{len(candidates)} merged, {len(reranked)} after rerank"
    )
    return reranked, timings


def retrieve_dense_only(query: str, k: int = DEFAULT_K, doc_id: str | None = None,
                        score_threshold: float | None = DEFAULT_SCORE_THRESHOLD) -> tuple[list[dict], dict]:
    """Retrieve top-k chunks using dense (embedding) similarity only, with reranking."""
    from reranker import rerank

    timings = {}

    start = time.time()
    query_embedding = embed_query(query)
    timings["embed_query_ms"] = int((time.time() - start) * 1000)

    start = time.time()
    results = query_dense(query_embedding, k=k * 2, doc_id=doc_id)
    timings["dense_search_ms"] = int((time.time() - start) * 1000)

    for chunk in results:
        chunk["dense_score"] = chunk.get("score", 0)

    reranked, rerank_ms, candidates_total = rerank(query, results, top_k=k, score_threshold=score_threshold)
    timings["rerank_ms"] = rerank_ms
    timings["candidates_total"] = candidates_total
    timings["candidates_kept"] = len(reranked)

    for chunk in reranked:
        chunk["score"] = chunk["rerank_score"]

    return reranked, timings


def retrieve_bm25_only(query: str, k: int = DEFAULT_K, doc_id: str | None = None,
                       score_threshold: float | None = DEFAULT_SCORE_THRESHOLD) -> tuple[list[dict], dict]:
    """Retrieve top-k chunks using BM25 keyword matching only, with reranking."""
    from reranker import rerank

    timings = {}

    start = time.time()
    results = query_bm25(query, k=k * 2, doc_id=doc_id)
    timings["bm25_search_ms"] = int((time.time() - start) * 1000)

    for chunk in results:
        chunk["bm25_score_raw"] = chunk.get("score", 0)

    reranked, rerank_ms, candidates_total = rerank(query, results, top_k=k, score_threshold=score_threshold)
    timings["rerank_ms"] = rerank_ms
    timings["candidates_total"] = candidates_total
    timings["candidates_kept"] = len(reranked)

    for chunk in reranked:
        chunk["score"] = chunk["rerank_score"]

    return reranked, timings
