from unittest.mock import patch, MagicMock
from retriever import retrieve_hybrid


DENSE_RESULTS = [
    {"chunk_id": "c1", "text": "ML text", "score": 0.9, "doc_id": "d1", "page_num": 1, "source": "d1, page 1", "token_count": 5},
    {"chunk_id": "c2", "text": "NLP text", "score": 0.7, "doc_id": "d1", "page_num": 2, "source": "d1, page 2", "token_count": 5},
    {"chunk_id": "c3", "text": "CV text", "score": 0.5, "doc_id": "d1", "page_num": 3, "source": "d1, page 3", "token_count": 5},
]

BM25_RESULTS = [
    {"chunk_id": "c2", "text": "NLP text", "score": 3.1, "doc_id": "d1", "page_num": 2, "source": "d1, page 2", "token_count": 5},
    {"chunk_id": "c4", "text": "RL text", "score": 2.0, "doc_id": "d1", "page_num": 4, "source": "d1, page 4", "token_count": 5},
    {"chunk_id": "c1", "text": "ML text", "score": 1.5, "doc_id": "d1", "page_num": 1, "source": "d1, page 1", "token_count": 5},
]


def _mock_rerank(query, chunks, top_k=5, score_threshold=0.3):
    for i, c in enumerate(chunks):
        c["rerank_score"] = round(0.9 - i * 0.1, 4)
    return chunks[:top_k], 10, len(chunks)


@patch("reranker.rerank", side_effect=_mock_rerank)
@patch("retriever.query_bm25", return_value=BM25_RESULTS)
@patch("retriever.query_dense", return_value=DENSE_RESULTS)
@patch("retriever.embed_query", return_value=[0.1] * 384)
def test_hybrid_merges_results(mock_embed, mock_dense, mock_bm25, mock_rerank):
    results, timings = retrieve_hybrid("test query", k=3)
    assert len(results) == 3
    ids = [r["chunk_id"] for r in results]
    assert "c1" in ids or "c2" in ids
    assert isinstance(timings, dict)


@patch("reranker.rerank", side_effect=_mock_rerank)
@patch("retriever.query_bm25", return_value=BM25_RESULTS)
@patch("retriever.query_dense", return_value=DENSE_RESULTS)
@patch("retriever.embed_query", return_value=[0.1] * 384)
def test_hybrid_rrf_scores_are_set(mock_embed, mock_dense, mock_bm25, mock_rerank):
    results, timings = retrieve_hybrid("test query", k=4)
    for r in results:
        assert "score" in r
        assert r["score"] > 0


@patch("reranker.rerank", side_effect=_mock_rerank)
@patch("retriever.query_bm25", return_value=[])
@patch("retriever.query_dense", return_value=DENSE_RESULTS)
@patch("retriever.embed_query", return_value=[0.1] * 384)
def test_hybrid_with_empty_bm25(mock_embed, mock_dense, mock_bm25, mock_rerank):
    results, timings = retrieve_hybrid("test query", k=2)
    assert len(results) == 2
    assert results[0]["chunk_id"] in ["c1", "c2", "c3"]


@patch("reranker.rerank", side_effect=_mock_rerank)
@patch("retriever.query_bm25", return_value=BM25_RESULTS)
@patch("retriever.query_dense", return_value=DENSE_RESULTS)
@patch("retriever.embed_query", return_value=[0.1] * 384)
def test_hybrid_returns_timings(mock_embed, mock_dense, mock_bm25, mock_rerank):
    results, timings = retrieve_hybrid("test query", k=3)
    assert "embed_query_ms" in timings
    assert "dense_search_ms" in timings
    assert "bm25_search_ms" in timings
    assert "rerank_ms" in timings


MULTI_DOC_DENSE = [
    {"chunk_id": "c1", "text": "ML text", "score": 0.9, "doc_id": "d1", "page_num": 1, "source": "d1, page 1", "token_count": 5},
    {"chunk_id": "c5", "text": "Other text", "score": 0.8, "doc_id": "d2", "page_num": 1, "source": "d2, page 1", "token_count": 5},
]

MULTI_DOC_BM25 = [
    {"chunk_id": "c2", "text": "NLP text", "score": 3.1, "doc_id": "d1", "page_num": 2, "source": "d1, page 2", "token_count": 5},
    {"chunk_id": "c6", "text": "D2 text", "score": 2.5, "doc_id": "d2", "page_num": 2, "source": "d2, page 2", "token_count": 5},
]


def _mock_rerank_multi(query, chunks, top_k=5, score_threshold=0.1):
    for i, c in enumerate(chunks):
        c["rerank_score"] = round(0.9 - i * 0.1, 4)
    return chunks[:top_k], 10, len(chunks)


@patch("reranker.rerank", side_effect=_mock_rerank_multi)
@patch("retriever.query_bm25", return_value=MULTI_DOC_BM25)
@patch("retriever.query_dense", return_value=MULTI_DOC_DENSE)
@patch("retriever.embed_query", return_value=[0.1] * 384)
def test_hybrid_passes_doc_id_to_searches(mock_embed, mock_dense, mock_bm25, mock_rerank):
    retrieve_hybrid("test query", k=5, doc_id="d1")
    _, dense_kwargs = mock_dense.call_args
    assert dense_kwargs.get("doc_id") == "d1"
    _, bm25_kwargs = mock_bm25.call_args
    assert bm25_kwargs.get("doc_id") == "d1"
