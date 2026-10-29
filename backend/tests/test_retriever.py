from unittest.mock import patch
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


@patch("retriever.query_bm25", return_value=BM25_RESULTS)
@patch("retriever.query_dense", return_value=DENSE_RESULTS)
@patch("retriever.embed_query", return_value=[0.1] * 384)
def test_hybrid_merges_results(mock_embed, mock_dense, mock_bm25):
    results = retrieve_hybrid("test query", k=3)
    assert len(results) == 3
    ids = [r["chunk_id"] for r in results]
    # c1 and c2 appear in both lists so should rank highest
    assert "c1" in ids
    assert "c2" in ids


@patch("retriever.query_bm25", return_value=BM25_RESULTS)
@patch("retriever.query_dense", return_value=DENSE_RESULTS)
@patch("retriever.embed_query", return_value=[0.1] * 384)
def test_hybrid_rrf_scores_are_set(mock_embed, mock_dense, mock_bm25):
    results = retrieve_hybrid("test query", k=4)
    for r in results:
        assert "score" in r
        assert r["score"] > 0


@patch("retriever.query_bm25", return_value=[])
@patch("retriever.query_dense", return_value=DENSE_RESULTS)
@patch("retriever.embed_query", return_value=[0.1] * 384)
def test_hybrid_with_empty_bm25(mock_embed, mock_dense, mock_bm25):
    results = retrieve_hybrid("test query", k=2)
    assert len(results) == 2
    # Should still return dense results
    assert results[0]["chunk_id"] in ["c1", "c2", "c3"]
