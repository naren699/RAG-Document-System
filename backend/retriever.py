from embedder import embed_query
from vector_store import query_dense
from bm25_retriever import query_bm25
import logging

logger = logging.getLogger(__name__)

DEFAULT_K = 5


def retrieve_hybrid(query: str, k: int = DEFAULT_K, doc_id: str | None = None) -> list[dict]:
    """Hybrid retrieval using Reciprocal Rank Fusion (RRF) of dense + BM25."""
    dense_results = query_dense(embed_query(query), k=k * 2, doc_id=doc_id)
    bm25_results = query_bm25(query, k=k * 2, doc_id=doc_id)

    rrf_scores = {}
    chunk_data = {}
    rrf_k = 60

    for rank, chunk in enumerate(dense_results):
        cid = chunk["chunk_id"]
        rrf_scores[cid] = rrf_scores.get(cid, 0) + 1 / (rrf_k + rank + 1)
        chunk_data[cid] = chunk
        chunk_data[cid]["dense_rank"] = rank + 1

    for rank, chunk in enumerate(bm25_results):
        cid = chunk["chunk_id"]
        rrf_scores[cid] = rrf_scores.get(cid, 0) + 1 / (rrf_k + rank + 1)
        if cid not in chunk_data:
            chunk_data[cid] = chunk
        chunk_data[cid]["bm25_rank"] = rank + 1

    max_rrf = 2 / (rrf_k + 1)
    for cid in rrf_scores:
        rrf_scores[cid] = min(rrf_scores[cid] / max_rrf, 1.0)

    sorted_ids = sorted(rrf_scores, key=lambda x: rrf_scores[x], reverse=True)

    results = []
    for cid in sorted_ids[:k]:
        chunk = chunk_data[cid]
        chunk["score"] = round(rrf_scores[cid], 4)
        chunk.pop("dense_rank", None)
        chunk.pop("bm25_rank", None)
        results.append(chunk)

    logger.info(
        f"Hybrid retrieval for '{query[:50]}...': "
        f"{len(dense_results)} dense, {len(bm25_results)} BM25, {len(results)} merged"
    )
    return results


def retrieve_dense_only(query: str, k: int = DEFAULT_K, doc_id: str | None = None) -> list[dict]:
    """Retrieve top-k chunks using dense (embedding) similarity only."""
    return query_dense(embed_query(query), k=k, doc_id=doc_id)


def retrieve_bm25_only(query: str, k: int = DEFAULT_K, doc_id: str | None = None) -> list[dict]:
    """Retrieve top-k chunks using BM25 keyword matching only."""
    return query_bm25(query, k=k, doc_id=doc_id)
