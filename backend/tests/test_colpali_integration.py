from unittest.mock import patch, MagicMock
import os


@patch.dict(os.environ, {"COLPALI_ENABLED": "true"})
@patch("vector_store.add_visual_chunks")
def test_visual_chunks_use_separate_collection(mock_add_visual):
    from vector_store import add_visual_chunks

    chunks = [{"chunk_id": "v1", "doc_id": "d1", "page_num": 1, "text": "[Visual]",
               "token_count": 0, "source": "d1, page 1", "page_type": "visual",
               "image_path": "page_images/d1_page_1.png"}]
    embeddings = [[0.1] * 128]
    add_visual_chunks(chunks, embeddings)
    mock_add_visual.assert_called_once_with(chunks, embeddings)


@patch("retriever.query_visual")
@patch("retriever.embed_query")
@patch("retriever.query_dense")
@patch("retriever.query_bm25")
@patch("reranker.rerank")
def test_retrieve_visual_disabled_returns_empty(mock_rerank, mock_bm25, mock_dense, mock_embed, mock_qv):
    mock_embed.return_value = [0.1] * 384
    chunk = {"chunk_id": "c1", "text": "t", "score": 0.9, "doc_id": "d1",
             "page_num": 1, "source": "s", "token_count": 5, "rerank_score": 0.8}
    mock_dense.return_value = [chunk]
    mock_bm25.return_value = []
    mock_rerank.return_value = ([chunk], 10, 1)

    import retriever
    old_val = retriever.COLPALI_ENABLED
    retriever.COLPALI_ENABLED = False
    try:
        from retriever import retrieve_hybrid
        results, _ = retrieve_hybrid("test", k=3)
        mock_qv.assert_not_called()
    finally:
        retriever.COLPALI_ENABLED = old_val


@patch("colpali_processor.embed_query_colpali", return_value=[0.1] * 128)
@patch("retriever.query_visual")
@patch("retriever.embed_query")
@patch("retriever.query_dense")
@patch("retriever.query_bm25")
@patch("reranker.rerank")
def test_retrieve_merges_visual_and_text(mock_rerank, mock_bm25, mock_dense, mock_embed, mock_qv, mock_colpali_embed):
    text_chunk = {"chunk_id": "c1", "text": "text chunk", "score": 0.8,
                  "doc_id": "d1", "page_num": 1, "source": "s", "token_count": 50,
                  "rerank_score": 0.8}
    mock_embed.return_value = [0.1] * 384
    mock_dense.return_value = [text_chunk]
    mock_bm25.return_value = []
    mock_rerank.return_value = ([text_chunk], 10, 1)

    visual_chunk = {"chunk_id": "v1", "text": "[Visual]", "score": 0.7,
                    "doc_id": "d1", "page_num": 2, "source": "s", "page_type": "visual"}
    mock_qv.return_value = [visual_chunk]

    import retriever
    old_val = retriever.COLPALI_ENABLED
    retriever.COLPALI_ENABLED = True
    try:
        from retriever import retrieve_hybrid
        results, _ = retrieve_hybrid("test", k=3)
        ids = [r["chunk_id"] for r in results]
        assert "c1" in ids
        assert "v1" in ids
    finally:
        retriever.COLPALI_ENABLED = old_val
