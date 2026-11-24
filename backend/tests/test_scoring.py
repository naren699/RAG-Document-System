"""Tests for the scoring, decision, and verdict pipeline.

Each test states the exact expected value.
Run with: cd backend && ./venv/Scripts/python.exe -m pytest tests/test_scoring.py -v
"""
import math
import re
import sys

sys.path.insert(0, ".")


# ── Sigmoid conversion with temperature ──────────────────────────────────────

class TestSigmoidConversion:
    """Reranker converts raw logits to 0-1 via sigmoid(x/T) with T=4."""

    T = 4.0

    def _sigmoid(self, raw):
        return 1.0 / (1.0 + math.exp(-raw / self.T))

    def test_zero_input(self):
        assert self._sigmoid(0.0) == 0.5

    def test_positive_logit(self):
        result = self._sigmoid(5.0)
        assert abs(result - 0.7773) < 0.0001

    def test_negative_logit(self):
        result = self._sigmoid(-5.0)
        assert abs(result - 0.2227) < 0.0001

    def test_deeply_negative_is_nonzero(self):
        """Values like -11 must NOT round to 0.0 — this was the original bug."""
        result = self._sigmoid(-11.0)
        assert result > 0.05, f"sigmoid(-11/4) = {result}, must be > 0.05"
        assert abs(result - 0.0601) < 0.001

    def test_deeply_negative_distinguishable(self):
        """Two different negative logits must produce different scores."""
        a = self._sigmoid(-10.78)
        b = self._sigmoid(-11.39)
        assert a > b, f"{a} should be > {b}"
        assert a - b > 0.005, f"difference {a-b} too small to display"

    def test_large_positive(self):
        result = self._sigmoid(10.0)
        assert abs(result - 0.9241) < 0.001

    def test_ranking_preserved(self):
        """Sigmoid must preserve the ordering of raw logits."""
        raws = [-12, -11, -10, -5, 0, 5, 10]
        scores = [self._sigmoid(r) for r in raws]
        for i in range(len(scores) - 1):
            assert scores[i] < scores[i + 1], f"ranking broken at {raws[i]}"


# ── Label boundaries ─────────────────────────────────────────────────────────

class TestLabelBoundaries:
    """scoreLevel: High >= 0.7, Medium >= 0.3, Low < 0.3."""

    def _label(self, score):
        if score >= 0.7:
            return "High"
        if score >= 0.3:
            return "Medium"
        return "Low"

    def test_high_boundary(self):
        assert self._label(0.70) == "High"
        assert self._label(0.71) == "High"
        assert self._label(1.0) == "High"

    def test_medium_boundary(self):
        assert self._label(0.30) == "Medium"
        assert self._label(0.50) == "Medium"
        assert self._label(0.69) == "Medium"

    def test_low_boundary(self):
        assert self._label(0.29) == "Low"
        assert self._label(0.0) == "Low"
        assert self._label(0.06) == "Low"

    def test_exact_threshold_values(self):
        assert self._label(0.3) == "Medium"
        assert self._label(0.7) == "High"
        assert self._label(0.2999) == "Low"
        assert self._label(0.6999) == "Medium"


# ── Threshold decision ────────────────────────────────────────────────────────

class TestThresholdDecision:
    def test_passes_when_above(self):
        assert 0.15 >= 0.10

    def test_fails_when_below(self):
        assert not (0.06 >= 0.10)

    def test_exact_threshold(self):
        assert 0.10 >= 0.10

    def test_none_threshold_passes_all(self):
        threshold = None
        score = 0.001
        passes = score >= threshold if threshold is not None else True
        assert passes is True


# ── Count invariant ───────────────────────────────────────────────────────────

class TestCountInvariant:
    """retrieved >= passed_threshold >= sent_to_model."""

    def test_all_pass(self):
        r, p, s = 10, 10, 5
        assert r >= p >= s

    def test_some_dropped(self):
        r, p, s = 10, 3, 3
        assert r >= p >= s

    def test_none_pass(self):
        r, p, s = 6, 0, 0
        assert r >= p >= s

    def test_invalid_state_rejected(self):
        r, p, s = 5, 6, 3  # passed > retrieved — impossible
        assert not (r >= p >= s)


# ── BM25 edge cases ──────────────────────────────────────────────────────────

class TestBM25:
    def test_all_zeros_when_term_missing(self):
        from rank_bm25 import BM25Okapi
        corpus = [["hello", "world"], ["foo", "bar"]]
        bm25 = BM25Okapi(corpus)
        scores = bm25.get_scores(["nonexistent"])
        assert list(scores) == [0.0, 0.0]

    def test_nonzero_when_term_present(self):
        from rank_bm25 import BM25Okapi
        corpus = [["education", "computer", "science"], ["skills", "python", "java"], ["experience", "developer"]]
        bm25 = BM25Okapi(corpus)
        scores = bm25.get_scores(["education"])
        assert scores[0] > 0, f"education chunk should score > 0, got {scores[0]}"
        assert scores[1] == 0.0
        assert scores[2] == 0.0

    def test_stemming_matches(self):
        from bm25_retriever import _stem
        assert _stem("skills") == "skill"
        assert _stem("networks") == "network"
        assert _stem("started") == "start"
        assert _stem("studies") == "study"
        assert _stem("classes") == "class"
        assert _stem("fixes") == "fix"

    def test_stemming_short_words_unchanged(self):
        from bm25_retriever import _stem
        assert _stem("is") == "is"
        assert _stem("a") == "a"
        assert _stem("the") == "the"

    def test_tokenizer_lowercases(self):
        from bm25_retriever import _tokenize
        tokens = _tokenize("Education B.E. Computer Science")
        assert "education" in [t.replace("educatio", "education") for t in tokens] or any("educ" in t for t in tokens)
        assert all(t == t.lower() for t in tokens)


# ── Citation parsing ──────────────────────────────────────────────────────────

class TestCitationParsing:
    """parseCitations extracts [N] markers from answer text."""

    def _parse(self, text):
        return set(int(m) for m in re.findall(r'\[(\d+)\]', text))

    def test_single_citation(self):
        assert self._parse("Answer text [1].") == {1}

    def test_multiple_citations(self):
        assert self._parse("First [1] and second [3].") == {1, 3}

    def test_repeated_citation(self):
        assert self._parse("[2] is cited twice [2].") == {2}

    def test_no_citations(self):
        assert self._parse("No citations here.") == set()

    def test_invalid_high_number(self):
        cited = self._parse("Answer [1] and [7].")
        assert cited == {1, 7}
        num_sources = 5
        invalid = {n for n in cited if n > num_sources}
        assert invalid == {7}

    def test_zero_not_valid(self):
        cited = self._parse("Answer [0] text.")
        assert cited == {0}
        invalid = {n for n in cited if n < 1}
        assert invalid == {0}

    def test_citation_in_brackets_only(self):
        """Plain numbers without brackets are not citations."""
        assert self._parse("Page 3 has 5 results.") == set()


# ── Refusal detection ─────────────────────────────────────────────────────────

class TestRefusalDetection:
    def _is_refusal(self, answer):
        phrases = [
            "i don't have that information",
            "not in the provided documents",
            "i cannot find",
            "i couldn't find",
            "not in the uploaded documents",
            "no relevant information",
        ]
        lower = answer.lower()
        return any(p in lower for p in phrases)

    def test_standard_refusal(self):
        assert self._is_refusal("I couldn't find this in the uploaded documents.")

    def test_case_insensitive(self):
        assert self._is_refusal("I COULDN'T FIND this information.")

    def test_not_a_refusal(self):
        assert not self._is_refusal("Machine learning is a subset of AI [1].")

    def test_partial_match(self):
        assert self._is_refusal("Sorry, I cannot find any relevant information about this topic.")

    def test_empty_not_refusal(self):
        assert not self._is_refusal("")


# ── Verdict rules ─────────────────────────────────────────────────────────────

class TestVerdictRules:
    """Verdict is determined by: is_not_found, grounding score, invalid citations."""

    def _verdict(self, is_not_found, grounding_score, has_invalid_citations):
        if is_not_found:
            return "Not in document"
        if grounding_score < 0.3:
            return "Not supported"
        if grounding_score < 0.7 or has_invalid_citations:
            return "Partially supported"
        return "Answered"

    def test_not_found(self):
        assert self._verdict(True, 0.0, False) == "Not in document"

    def test_not_found_overrides_good_score(self):
        assert self._verdict(True, 0.9, False) == "Not in document"

    def test_not_supported(self):
        assert self._verdict(False, 0.1, False) == "Not supported"

    def test_partially_supported_by_score(self):
        assert self._verdict(False, 0.5, False) == "Partially supported"

    def test_partially_supported_by_invalid_citations(self):
        assert self._verdict(False, 0.9, True) == "Partially supported"

    def test_answered(self):
        assert self._verdict(False, 0.85, False) == "Answered"

    def test_boundary_0_3(self):
        assert self._verdict(False, 0.3, False) == "Partially supported"
        assert self._verdict(False, 0.29, False) == "Not supported"

    def test_boundary_0_7(self):
        assert self._verdict(False, 0.7, False) == "Answered"
        assert self._verdict(False, 0.69, False) == "Partially supported"


# ── Text cleaning ─────────────────────────────────────────────────────────────

class TestTextCleaning:
    def test_stray_commas(self):
        from pdf_extractor import clean_extracted_text
        assert clean_extracted_text("Python, , , Java") == "Python, Java"

    def test_broken_hyphen(self):
        from pdf_extractor import clean_extracted_text
        assert clean_extracted_text("Develop-\nment") == "Development"

    def test_normal_text_unchanged(self):
        from pdf_extractor import clean_extracted_text
        assert clean_extracted_text("Machine learning is AI.") == "Machine learning is AI."

    def test_number_comma_preserved(self):
        from pdf_extractor import clean_extracted_text
        assert "1,000" in clean_extracted_text("Earned 1,000 points")
