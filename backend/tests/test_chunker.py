import pytest
from chunker import chunk_text, count_tokens, chunk_document, _get_overlap, _encoder


class TestCountTokens:
    def test_empty_string(self):
        assert count_tokens("") == 0

    def test_simple_text(self):
        tokens = count_tokens("Hello world")
        assert tokens > 0

    def test_consistent(self):
        text = "The quick brown fox jumps over the lazy dog."
        assert count_tokens(text) == count_tokens(text)


class TestChunkText:
    def test_empty_input(self):
        assert chunk_text("") == []

    def test_whitespace_only(self):
        assert chunk_text("   \n\n  ") == []

    def test_short_text_single_chunk(self):
        text = "A short paragraph."
        chunks = chunk_text(text, chunk_size=500)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_splits_at_paragraph_boundary(self):
        para1 = "First paragraph. " * 30  # ~60 tokens
        para2 = "Second paragraph. " * 30
        text = para1.strip() + "\n\n" + para2.strip()
        chunks = chunk_text(text, chunk_size=80, chunk_overlap=0)
        assert len(chunks) >= 2

    def test_overlap_present(self):
        para1 = "Alpha bravo charlie. " * 25
        para2 = "Delta echo foxtrot. " * 25
        text = para1.strip() + "\n\n" + para2.strip()
        chunks = chunk_text(text, chunk_size=40, chunk_overlap=10)
        if len(chunks) >= 2:
            # Overlap means some tokens from end of chunk1 appear in start of chunk2
            last_tokens_1 = set(_encoder.encode(chunks[0])[-10:])
            first_tokens_2 = set(_encoder.encode(chunks[1])[:15])
            assert last_tokens_1 & first_tokens_2, "Expected overlap tokens"

    def test_respects_chunk_size(self):
        text = "Word. " * 500
        chunks = chunk_text(text, chunk_size=100, chunk_overlap=10)
        for chunk in chunks:
            token_count = count_tokens(chunk)
            assert token_count <= 130, f"Chunk has {token_count} tokens, expected <= ~130"


class TestGetOverlap:
    def test_zero_overlap(self):
        assert _get_overlap("hello world", 0) == ""

    def test_full_text_shorter_than_overlap(self):
        result = _get_overlap("hi", 100)
        assert result == "hi"

    def test_returns_last_n_tokens(self):
        text = "alpha bravo charlie delta echo"
        result = _get_overlap(text, 2)
        assert "echo" in result


class TestChunkDocument:
    def test_empty_pages(self):
        pages = [{"page_num": 1, "text": "", "has_text": False}]
        chunks = chunk_document(pages, "test_doc")
        assert chunks == []

    def test_single_page(self):
        pages = [{"page_num": 1, "text": "Some text here.", "has_text": True}]
        chunks = chunk_document(pages, "test_doc")
        assert len(chunks) == 1
        assert chunks[0]["chunk_id"] == "test_doc_chunk_0"
        assert chunks[0]["doc_id"] == "test_doc"
        assert chunks[0]["page_num"] == 1
        assert chunks[0]["text"] == "Some text here."
        assert chunks[0]["token_count"] > 0

    def test_multiple_pages(self):
        pages = [
            {"page_num": 1, "text": "Page one text.", "has_text": True},
            {"page_num": 2, "text": "Page two text.", "has_text": True},
        ]
        chunks = chunk_document(pages, "doc1")
        assert len(chunks) == 2
        assert chunks[0]["page_num"] == 1
        assert chunks[1]["page_num"] == 2
        assert chunks[0]["chunk_id"] == "doc1_chunk_0"
        assert chunks[1]["chunk_id"] == "doc1_chunk_1"

    def test_skips_empty_pages(self):
        pages = [
            {"page_num": 1, "text": "Has text.", "has_text": True},
            {"page_num": 2, "text": "", "has_text": False},
            {"page_num": 3, "text": "Also has text.", "has_text": True},
        ]
        chunks = chunk_document(pages, "doc2")
        assert len(chunks) == 2
        page_nums = [c["page_num"] for c in chunks]
        assert page_nums == [1, 3]
