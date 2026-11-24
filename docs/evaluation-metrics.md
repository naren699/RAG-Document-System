# FARE Evaluation Metrics Specification

> Targets set on: 2026-11-02 (proposed, pending approval)

## Overview

Ten metrics organized into four groups: **generation quality** (Accuracy, Faithfulness, Answer Relevance), **retrieval quality** (Context Relevance, Retrieval Precision@k, Retrieval Recall@k), **refusal behaviour** (Refusal Precision, Refusal Recall), and **agreement / overlap** (Human-Agreement Accuracy, Exact Match + Token F1).

---

## 1. Accuracy

| Field | Value |
|---|---|
| **Question it answers** | What fraction of all questions does the system handle correctly? |
| **Formula** | `Accuracy = (correct_answerable + correct_refusals) / total_questions` |
| **Data needed** | System answers, `answerable` flag per question, human label `correct` (yes/no) per answer |
| **Automatic or human-labeled** | Human-labeled. A human decides whether each answer is correct. |
| **Known limits** | Treats all questions equally regardless of difficulty. A correct refusal and a correct factual answer carry the same weight. The label `correct` is binary — partially correct answers are counted as incorrect unless the labeler judges them sufficient. |

A correct refusal means the system refused AND the question is unanswerable. A correct answer means the system answered AND a human labeled the answer correct. Accuracy is reported overall and split by answerable vs. unanswerable questions.

---

## 2. Faithfulness

| Field | Value |
|---|---|
| **Question it answers** | Are the claims in the system's answer actually supported by the retrieved chunks? |
| **Formula** | `Faithfulness = supported_claims / total_claims` |
| **Data needed** | System answer text, retrieved chunks, LLM judge verdicts per claim |
| **Automatic or human-labeled** | Automatic (LLM judge at temperature 0). |
| **Known limits** | Depends on claim decomposition quality — compound sentences may be split imperfectly. The judge uses the same LLM provider as generation, introducing possible self-consistency bias. Token-overlap heuristic from `grounding.py` is kept as a baseline for comparison. |

Process: (1) decompose the answer into atomic claims (one fact each) via LLM, (2) for each claim, the LLM judge decides whether any retrieved chunk supports it, returning `{supported, supporting_chunk_id, reason}`, (3) aggregate. Unsupported claims are surfaced in the UI with a warning icon.

---

## 3. Answer Relevance

| Field | Value |
|---|---|
| **Question it answers** | Does the system's answer actually address what was asked? |
| **Formula** | `Answer Relevance = relevant_answers / total_answers` |
| **Data needed** | Question text, system answer text, LLM judge verdict |
| **Automatic or human-labeled** | Automatic (LLM judge at temperature 0). |
| **Known limits** | Binary (relevant / not relevant) — does not capture degrees of relevance. A refusal to an unanswerable question is counted as relevant (correct behaviour), which can inflate the score if many questions are unanswerable. |

The judge decides whether the answer directly addresses the question. A refusal on an unanswerable question counts as relevant. A refusal on an answerable question counts as not relevant.

---

## 4. Context Relevance

| Field | Value |
|---|---|
| **Question it answers** | Were the retrieved chunks actually useful for answering the question? |
| **Formula** | `Context Relevance = relevant_chunks / retrieved_chunks` (averaged over all questions) |
| **Data needed** | Question text, retrieved chunk texts, LLM judge verdict per chunk |
| **Automatic or human-labeled** | Automatic (LLM judge at temperature 0). |
| **Known limits** | Evaluated per-chunk independently — does not capture whether the set of chunks collectively provides enough information. A chunk with partial relevance is counted as relevant (binary). |

For each (question, chunk) pair, the judge decides whether the chunk contains information that helps answer the question. The per-question ratio is averaged across all questions to produce the aggregate score.

---

## 5. Human-Agreement Accuracy

| Field | Value |
|---|---|
| **Question it answers** | How well do the LLM judge verdicts agree with independent human judgments? |
| **Formula** | `Human-Agreement Accuracy = matching_verdicts / compared_verdicts`. Also: Cohen's kappa `κ = (p_observed - p_expected) / (1 - p_expected)` between two human labelers. |
| **Data needed** | LLM judge verdicts (from metrics 2-4), two independent human label sets for the same 30 answers |
| **Automatic or human-labeled** | Human-labeled (requires two independent labelers). |
| **Known limits** | Sample of 30 may be too small for narrow confidence intervals. Kappa is sensitive to base rates — if most answers are correct, even random agreement is high. The comparison is per-verdict (faithful, answer_relevant, chunk_relevant), not per-answer. |

Two labelers independently label the same 30 system answers. Agreement is computed between: (a) judge vs. human-1, (b) judge vs. human-2, and (c) human-1 vs. human-2 (inter-rater reliability via Cohen's kappa).

---

## 6. Retrieval Precision@k

| Field | Value |
|---|---|
| **Question it answers** | What fraction of the top-k retrieved chunks are actually relevant to the question? |
| **Formula** | `Precision@k = |retrieved_top_k ∩ gold_chunk_ids| / k` (averaged over questions with gold chunks) |
| **Data needed** | Retrieved chunk IDs per question, `gold_chunk_ids` from labeled dataset |
| **Automatic or human-labeled** | Computed from gold data (gold_chunk_ids are set once during dataset labeling). |
| **Known limits** | Requires gold_chunk_ids to be populated — questions without gold chunks are excluded (reported via n). Gold chunks are tied to a specific document version and chunking configuration; re-chunking invalidates them. k is fixed at retrieval time (default 5). |

Only questions with at least one gold_chunk_id are included. The metric shows whether the retriever is surfacing the right chunks rather than just any chunks.

---

## 7. Retrieval Recall@k

| Field | Value |
|---|---|
| **Question it answers** | Of all the chunks that should have been retrieved, how many actually were? |
| **Formula** | `Recall@k = |retrieved_top_k ∩ gold_chunk_ids| / |gold_chunk_ids|` (averaged over questions with gold chunks) |
| **Data needed** | Retrieved chunk IDs per question, `gold_chunk_ids` from labeled dataset |
| **Automatic or human-labeled** | Computed from gold data. |
| **Known limits** | Same as Precision@k — depends on gold_chunk_ids quality. If the gold set is incomplete (relevant chunks were missed during labeling), recall will appear lower than reality. For questions with many gold chunks, high recall may require a large k. |

Complements Precision@k: a system that retrieves everything has 100% recall but low precision. Both are needed.

---

## 8. Refusal Precision

| Field | Value |
|---|---|
| **Question it answers** | When the system refuses to answer, is it right to refuse? |
| **Formula** | `Refusal Precision = correct_refusals / all_refusals` |
| **Data needed** | System answer (refusal detected via pattern matching), `answerable` flag per question |
| **Automatic or human-labeled** | Computed from gold data (`answerable` flag set during dataset labeling). Refusal detection is automatic (pattern matching on known refusal phrases). |
| **Known limits** | Refusal detection relies on substring matching against known phrases — a novel refusal phrasing could be missed. The `answerable` flag is binary — borderline questions are forced into one category. |

A correct refusal = the system refused AND the question is unanswerable. A false refusal (FP) = the system refused but the question was answerable.

---

## 9. Refusal Recall

| Field | Value |
|---|---|
| **Question it answers** | Of all unanswerable questions, how many does the system correctly refuse? |
| **Formula** | `Refusal Recall = correct_refusals / total_unanswerable` |
| **Data needed** | Same as Refusal Precision |
| **Automatic or human-labeled** | Computed from gold data. |
| **Known limits** | Same detection limits as Refusal Precision. A system that refuses everything has 100% recall but 0% precision on answerable questions. |

Together with Refusal Precision, forms the refusal confusion matrix:

|  | System Answers | System Refuses |
|---|---|---|
| **Answerable** | TN (correct answer attempt) | FP (wrong refusal) |
| **Unanswerable** | FN (should have refused) | TP (correct refusal) |

---

## 10. Exact Match + Token F1

| Field | Value |
|---|---|
| **Question it answers** | Does the system's answer match the expected gold answer word-for-word (EM) or at the token level (F1)? |
| **Formula — Exact Match** | `EM = 1 if normalize(prediction) == normalize(gold_answer), else 0` (averaged over questions with gold answers) |
| **Formula — Token F1** | `precision = |pred_tokens ∩ gold_tokens| / |pred_tokens|`, `recall = |pred_tokens ∩ gold_tokens| / |gold_tokens|`, `F1 = 2 * precision * recall / (precision + recall)` (averaged) |
| **Normalization** | Lowercase, strip punctuation, remove articles (a, an, the), collapse whitespace |
| **Data needed** | System answer text, `gold_answer` from labeled dataset |
| **Automatic or human-labeled** | Computed from gold data. |
| **Known limits** | EM is almost always 0 for open-ended or long-form answers — meaningful only for short factual questions (dates, names, numbers). Token F1 is more forgiving but still penalizes correct answers that use different wording. Neither metric captures semantic equivalence. |

Both metrics are reported. EM is flagged in the UI as primarily useful for short factual questions.

---

## Summary Table

| # | Metric | Type | Data Source | Target (proposed) |
|---|---|---|---|---|
| 1 | Accuracy | Human-labeled | human_verdicts.csv | >= 80% |
| 2 | Faithfulness | LLM judge | claims.json | >= 85% |
| 3 | Answer Relevance | LLM judge | relevance.json | >= 85% |
| 4 | Context Relevance | LLM judge | relevance.json | >= 70% |
| 5 | Human-Agreement Accuracy | Human-labeled (dual) | human_verdicts.csv + judge results | >= 80% |
| 6 | Retrieval Precision@k | Gold data | gold_chunk_ids | >= 60% |
| 7 | Retrieval Recall@k | Gold data | gold_chunk_ids | >= 80% |
| 8 | Refusal Precision | Gold data | answerable flag | >= 90% |
| 9 | Refusal Recall | Gold data | answerable flag | >= 90% |
| 10 | Exact Match + Token F1 | Gold data | gold_answer | F1 >= 50% (EM informational only) |
