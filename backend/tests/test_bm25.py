import pytest
from bm25_retriever import _tokenize, build_index, query_bm25, get_index_and_chunks


SAMPLE_CHUNKS = [
    {"chunk_id": "c1", "text": "Machine learning is a subset of artificial intelligence.", "doc_id": "doc1", "page_num": 1, "source": "doc1, page 1", "token_count": 10},
    {"chunk_id": "c2", "text": "Natural language processing deals with text analysis.", "doc_id": "doc1", "page_num": 2, "source": "doc1, page 2", "token_count": 9},
    {"chunk_id": "c3", "text": "Computer vision enables image classification and detection.", "doc_id": "doc1", "page_num": 3, "source": "doc1, page 3", "token_count": 8},
]


class TestTokenize:
    def test_simple(self):
        tokens = _tokenize("Hello World")
        assert tokens == ["hello", "world"]

    def test_punctuation_stripped(self):
        tokens = _tokenize("Hello, world! How are you?")
        assert "hello" in tokens
        assert "world" in tokens
        assert "," not in tokens

    def test_empty_string(self):
        assert _tokenize("") == []


class TestBuildAndQuery:
    def setup_method(self):
        build_index(SAMPLE_CHUNKS)

    def teardown_method(self):
        build_index([])

    def test_build_index(self):
        index, chunks = get_index_and_chunks()
        assert index is not None
        assert len(chunks) == 3

    def test_query_returns_results(self):
        results = query_bm25("machine learning", k=2)
        assert len(results) <= 2
        assert results[0]["chunk_id"] == "c1"

    def test_query_relevance_order(self):
        results = query_bm25("natural language processing text", k=3)
        assert results[0]["chunk_id"] == "c2"

    def test_query_with_doc_filter(self):
        results = query_bm25("machine learning", k=5, doc_id="nonexistent")
        assert len(results) == 0

    def test_empty_index(self):
        build_index([])
        results = query_bm25("anything")
        assert results == []

    def test_scores_are_float(self):
        results = query_bm25("image classification", k=1)
        assert len(results) == 1
        assert isinstance(results[0]["score"], float)
