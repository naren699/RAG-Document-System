from grounding import compute_grounding_score


class TestGroundingScore:
    def test_empty_answer(self):
        result = compute_grounding_score("", [{"text": "some content"}])
        assert result["score"] == 0.0

    def test_empty_chunks(self):
        result = compute_grounding_score("Some answer.", [])
        assert result["score"] == 0.0

    def test_well_grounded(self):
        chunks = [
            {"text": "Machine learning uses algorithms to learn patterns from data."},
            {"text": "Neural networks are a type of machine learning model."},
        ]
        answer = "Machine learning uses algorithms to learn patterns [1]. Neural networks are machine learning models [2]."
        result = compute_grounding_score(answer, chunks)
        assert result["score"] >= 0.5
        assert result["invalid_citations"] == []

    def test_invalid_citation(self):
        chunks = [{"text": "Only one chunk here."}]
        answer = "Something from source [1] and also from [3]."
        result = compute_grounding_score(answer, chunks)
        assert 3 in result["invalid_citations"]

    def test_no_citations_uses_all_chunks(self):
        chunks = [
            {"text": "Python programming language is versatile and popular."},
        ]
        answer = "Python programming language is popular and versatile."
        result = compute_grounding_score(answer, chunks)
        assert result["score"] >= 0.5

    def test_ungrounded_answer(self):
        chunks = [{"text": "The sky is blue."}]
        answer = "Quantum mechanics explains particle behavior through wave functions and probability distributions."
        result = compute_grounding_score(answer, chunks)
        assert result["score"] < 0.5
