# Phase 3 Testing Report

**Date:** 2026-10-12 18:05 UTC
**LLM Provider:** unknown
**Model:** unknown
**Queries:** 40 (0 in-scope, 0 out-of-scope, 0 adversarial, 40 errors)

## Documents Tested

  - `test_sample`: 5 chunks

## Key Metrics

| Metric | Value | Target |
|--------|-------|--------|
| Abstention Rate | 0.0% (0/0) | >= 90% |
| Hallucination Score | 100.0% | >= 85% |
| In-Scope Accuracy | 0.0% (0/0) | High |
| Avg Relevance Score | 0.000 | > 0.5 |

## Latency

| Metric | Value |
|--------|-------|
| Average Total | 0 ms |
| Median (P50) | 0 ms |
| P95 | 0 ms |
| Max | 0 ms |
| Avg Retrieval | 0 ms |
| Avg Generation | 0 ms |

## Token Usage

| Metric | Value |
|--------|-------|
| Avg Input Tokens | 0 |
| Avg Output Tokens | 0 |
| Total Input Tokens | 0 |
| Total Output Tokens | 0 |

## Results by Category

### Factual Queries (answer in document)

| ID | Query | Correct | Abstained | Relevance | Latency |
|----|-------|---------|-----------|-----------|---------|

### Out-of-Scope Queries (answer NOT in document)

| ID | Query | Abstained | Hallucination | Relevance | Latency |
|----|-------|-----------|---------------|-----------|---------|

### Adversarial Queries

| ID | Query | Abstained | Hallucination | Relevance | Latency |
|----|-------|-----------|---------------|-----------|---------|

### Errors

| ID | Query | Error |
|----|-------|-------|
| 1 | What is machine learning? | HTTP 429 after 3 retries |
| 2 | What is supervised learning? | HTTP 429 after 3 retries |
| 3 | What is unsupervised learning? | HTTP 429 after 3 retries |
| 4 | When did the field of machine learning grow rapidl | HTTP 429 after 3 retries |
| 5 | What are neural networks? | HTTP 429 after 3 retries |
| 6 | What is deep learning? | HTTP 429 after 3 retries |
| 7 | What are convolutional neural networks used for? | HTTP 429 after 3 retries |
| 8 | What is NLP? | HTTP 429 after 3 retries |
| 9 | What are key NLP tasks? | HTTP 429 after 3 retries |
| 10 | When did transformers revolutionize NLP? | HTTP 429 after 3 retries |
| 11 | What is computer vision? | HTTP 429 after 3 retries |
| 12 | What are CNNs? | HTTP 429 after 3 retries |
| 13 | What are applications of computer vision? | HTTP 500: Internal Server Error |
| 14 | What topics does this document cover? | HTTP 429 after 3 retries |
| 15 | What is discussed on page 1? | HTTP 429 after 3 retries |
| 16 | What is discussed on page 3? | HTTP 429 after 3 retries |
| 17 | What is discussed on page 4? | HTTP 429 after 3 retries |
| 18 | What is the relationship between AI and machine le | HTTP 429 after 3 retries |
| 19 | What types of learning are described? | HTTP 429 after 3 retries |
| 20 | What is sentiment analysis? | HTTP 429 after 3 retries |
| 21 | What is the capital of Mars? | HTTP 429 after 3 retries |
| 22 | What did Elon Musk tweet yesterday? | HTTP 429 after 3 retries |
| 23 | How do I make a chocolate cake? | HTTP 429 after 3 retries |
| 24 | What is the stock price of Apple today? | HTTP 429 after 3 retries |
| 25 | Who won the 2030 World Cup? | HTTP 429 after 3 retries |
| 26 | What is quantum computing? | HTTP 429 after 3 retries |
| 27 | Tell me about climate change policies in Antarctic | HTTP 429 after 3 retries |
| 28 | What is the meaning of life? | HTTP 429 after 3 retries |
| 29 | Write me a poem about the ocean. | HTTP 429 after 3 retries |
| 30 | What happens in chapter 47 of this document? | HTTP 429 after 3 retries |
| 31 | How do neural networks relate to both NLP and comp | HTTP 429 after 3 retries |
| 32 | Compare supervised and unsupervised learning. | HTTP 429 after 3 retries |
| 33 | What evidence supports the growth of machine learn | HTTP 429 after 3 retries |
| 34 | How are transformers and CNNs different in their a | HTTP 429 after 3 retries |
| 35 | Summarize all the main topics covered in this docu | HTTP 429 after 3 retries |
| 36 | The document says machine learning was invented in | HTTP 429 after 3 retries |
| 37 | Based on this document what will happen to AI in 2 | HTTP 429 after 3 retries |
| 38 | What does the author think about AI taking over th | HTTP 429 after 3 retries |
| 39 | Extrapolate the ML trends to predict which jobs wi | HTTP 429 after 3 retries |
| 40 | What are the hidden meanings in this document? | HTTP 429 after 3 retries |

## Observations

- **Abstention rate:** 0.0% — below the 90% target
- **Hallucination score:** 100.0% — meets the 85% target
- **Latency:** average 0ms — meets the 10s target
- **Token efficiency:** ~0 input tokens per query

## Known Limitations

- Evaluation is semi-automated: "is_correct" for in-scope queries is marked "likely" (not verified against ground truth)
- Hallucination detection relies on abstention pattern matching, not semantic verification
- Results depend on the specific PDF(s) ingested during testing
- BM25 index is rebuilt on startup; results may vary across restarts

## Next Steps

- [ ] Manual review of "likely correct" answers for actual correctness
- [ ] Add ground-truth answers to test-queries.csv for automated scoring
- [ ] Run ablation tests (Phase 4): dense-only vs BM25-only vs hybrid
- [ ] Test with multiple document types (reports, papers, manuals)
