from llm_provider import format_context, format_user_message, generate_answer


SAMPLE_CHUNKS = [
    {"source": "doc1, page 1", "score": 0.85, "text": "Machine learning is AI."},
    {"source": "doc1, page 2", "score": 0.72, "text": "NLP processes language."},
]


class TestFormatContext:
    def test_formats_sources(self):
        result = format_context(SAMPLE_CHUNKS)
        assert "[Source 1: doc1, page 1 | Relevance: 0.85]" in result
        assert "Machine learning is AI." in result
        assert "[Source 2: doc1, page 2 | Relevance: 0.72]" in result

    def test_empty_chunks(self):
        assert format_context([]) == ""

    def test_separator(self):
        result = format_context(SAMPLE_CHUNKS)
        assert "---" in result

    def test_missing_fields_use_defaults(self):
        chunks = [{"text": "Some text"}]
        result = format_context(chunks)
        assert "Relevance: 0.00" in result
        assert "page ?" in result


class TestFormatUserMessage:
    def test_contains_context_and_query(self):
        result = format_user_message("some context", "what is ML?")
        assert "some context" in result
        assert "what is ML?" in result
        assert "Context:" in result
        assert "Question:" in result
        assert "Answer:" in result


class TestGenerateAnswer:
    def test_empty_chunks_returns_abstention(self):
        result = generate_answer("any question", [])
        assert "don't have that information" in result["answer"]
        assert result["input_tokens"] == 0
        assert result["generation_time_ms"] == 0
