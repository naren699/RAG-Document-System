import json
import logging
import re
from pathlib import Path

logger = logging.getLogger("fare.eval.judge")

CLAIMS_SPLIT_PROMPT_VERSION = "claims_split_v1"
FAITHFULNESS_PROMPT_VERSION = "faithfulness_v1"
ANSWER_RELEVANCE_PROMPT_VERSION = "answer_relevance_v1"
CONTEXT_RELEVANCE_PROMPT_VERSION = "context_relevance_v1"

CLAIMS_SPLIT_SYSTEM = """You are an evaluation assistant. Your task is to decompose an answer into atomic claims.

Each atomic claim is a single factual statement that can be independently verified as true or false.
Compound sentences must be split into separate claims.

Rules:
- Each claim should contain exactly one piece of information.
- Preserve the original meaning — do not add or remove information.
- Drop filler phrases like "Based on the document" or "According to the context".
- If the answer is a refusal (e.g., "I couldn't find this"), return a single claim with that text.
- Output ONLY a JSON array of strings. No other text."""

CLAIMS_SPLIT_USER = """Split this answer into atomic claims:

{answer}

JSON array:"""

FAITHFULNESS_SYSTEM = """You are an evaluation judge. You must determine whether a claim is supported by the provided context chunks.

Rules:
- A claim is SUPPORTED only if the context directly states or clearly implies the information.
- Do NOT use your own knowledge. Only the provided context matters.
- If the claim is only partially supported, mark as NOT supported and explain what is missing.
- Output ONLY valid JSON. No other text."""

FAITHFULNESS_USER = """Claim: {claim}

Context chunks:
{chunks}

Is this claim supported by the context? Respond with JSON:
{{"supported": true or false, "supporting_chunk_id": "chunk_id or null", "reason": "brief explanation"}}"""


def _parse_json(text: str) -> dict | list | None:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'[\[{].*[\]}]', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return None


def _fallback_split_claims(answer: str) -> list[str]:
    """Sentence-level splitting as fallback — mirrors grounding.py _split_claims."""
    claims = []
    for line in answer.split('\n'):
        line = line.strip()
        if not line:
            continue
        bullet = re.match(r'^[\s]*[*\-•]\s+', line)
        if bullet:
            claim = line[bullet.end():].strip()
            if claim:
                claims.append(claim)
        else:
            for sent in re.split(r'(?<=[.!?])\s+', line):
                sent = sent.strip()
                if sent:
                    claims.append(sent)
    return claims if claims else [answer.strip()]


def split_into_atomic_claims(answer: str) -> list[str]:
    from llm_provider import call_llm_raw

    try:
        result = call_llm_raw(
            system_prompt=CLAIMS_SPLIT_SYSTEM,
            user_message=CLAIMS_SPLIT_USER.format(answer=answer),
            temperature=0,
            max_tokens=1024,
        )
        parsed = _parse_json(result["text"])
        if isinstance(parsed, list) and len(parsed) > 0:
            return [str(c) for c in parsed if str(c).strip()]
    except Exception as e:
        logger.warning(f"LLM claim splitting failed, using fallback: {e}")

    return _fallback_split_claims(answer)


def judge_claim_faithfulness(claim: str, chunks: list[dict]) -> dict:
    from llm_provider import call_llm_raw

    chunks_text = "\n\n".join(
        f"[chunk_id: {c.get('chunk_id', 'unknown')}]\n{c.get('text', '')[:800]}"
        for c in chunks
    )

    result = call_llm_raw(
        system_prompt=FAITHFULNESS_SYSTEM,
        user_message=FAITHFULNESS_USER.format(claim=claim, chunks=chunks_text),
        temperature=0,
        max_tokens=256,
    )

    parsed = _parse_json(result["text"])
    if isinstance(parsed, dict):
        return {
            "supported": bool(parsed.get("supported", False)),
            "supporting_chunk_id": parsed.get("supporting_chunk_id"),
            "reason": str(parsed.get("reason", "")),
        }

    return {"supported": False, "supporting_chunk_id": None, "reason": "Failed to parse judge response"}


def evaluate_faithfulness(run_id: str) -> dict:
    from eval.runner import RUNS_DIR

    run_dir = RUNS_DIR / run_id
    answers_path = run_dir / "answers.json"
    claims_path = run_dir / "claims.json"

    if not answers_path.exists():
        raise FileNotFoundError(f"No answers.json for run {run_id}")

    answers = json.loads(answers_path.read_text(encoding="utf-8"))

    all_claims = []
    total_claims = 0
    supported_claims = 0
    evaluated_answers = 0

    for ans in answers:
        if ans.get("is_refusal"):
            all_claims.append({
                "question_id": ans["question_id"],
                "answer_id": ans["answer_id"],
                "is_refusal": True,
                "claims": [],
                "faithfulness_score": None,
            })
            continue

        answer_text = ans.get("answer_text", "")
        chunks = ans.get("retrieved_chunks", [])
        if not answer_text or not chunks:
            continue

        logger.info(f"Faithfulness: evaluating answer {ans['answer_id']}")
        claims = split_into_atomic_claims(answer_text)

        claim_verdicts = []
        for claim in claims:
            verdict = judge_claim_faithfulness(claim, chunks)
            claim_verdicts.append({
                "text": claim,
                **verdict,
            })
            total_claims += 1
            if verdict["supported"]:
                supported_claims += 1

        n_supported = sum(1 for c in claim_verdicts if c["supported"])
        score = n_supported / len(claim_verdicts) if claim_verdicts else 0.0

        all_claims.append({
            "question_id": ans["question_id"],
            "answer_id": ans["answer_id"],
            "is_refusal": False,
            "claims": claim_verdicts,
            "faithfulness_score": round(score, 4),
        })
        evaluated_answers += 1

    result = {
        "run_id": run_id,
        "judge_prompt_version": FAITHFULNESS_PROMPT_VERSION,
        "claims_split_version": CLAIMS_SPLIT_PROMPT_VERSION,
        "results": all_claims,
    }

    with open(claims_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str)

    faithfulness_scores = [r["faithfulness_score"] for r in all_claims
                          if r["faithfulness_score"] is not None]
    avg_faithfulness = (sum(faithfulness_scores) / len(faithfulness_scores)
                        if faithfulness_scores else None)

    return {
        "faithfulness": round(avg_faithfulness, 4) if avg_faithfulness is not None else None,
        "n": evaluated_answers,
        "total_claims": total_claims,
        "supported_claims": supported_claims,
        "judge_prompt_version": FAITHFULNESS_PROMPT_VERSION,
    }


# ---------------------------------------------------------------------------
# Answer Relevance
# ---------------------------------------------------------------------------

ANSWER_RELEVANCE_SYSTEM = """You are an evaluation judge. Determine whether the answer is relevant to the question.

Rules:
- An answer is RELEVANT if it directly addresses what the question asks.
- A refusal (e.g., "I couldn't find this in the uploaded documents") to a question that cannot be answered from the provided documents IS relevant — it is the correct response.
- An answer that discusses a related topic but does not answer the specific question is NOT relevant.
- An answer that only partially addresses the question is still RELEVANT if it acknowledges the partial coverage.
- Output ONLY valid JSON. No other text."""

ANSWER_RELEVANCE_USER = """Question: {question}
Answer: {answer}

Is this answer relevant to the question? Respond with JSON:
{{"relevant": true or false, "reason": "brief explanation"}}"""


def judge_answer_relevance(question: str, answer: str) -> dict:
    from llm_provider import call_llm_raw

    result = call_llm_raw(
        system_prompt=ANSWER_RELEVANCE_SYSTEM,
        user_message=ANSWER_RELEVANCE_USER.format(question=question, answer=answer),
        temperature=0,
        max_tokens=256,
    )

    parsed = _parse_json(result["text"])
    if isinstance(parsed, dict):
        return {
            "relevant": bool(parsed.get("relevant", False)),
            "reason": str(parsed.get("reason", "")),
        }

    return {"relevant": False, "reason": "Failed to parse judge response"}


# ---------------------------------------------------------------------------
# Context Relevance
# ---------------------------------------------------------------------------

CONTEXT_RELEVANCE_SYSTEM = """You are an evaluation judge. Determine whether a text chunk contains information relevant to answering the given question.

Rules:
- A chunk is RELEVANT if it contains information that would help answer the question, even partially.
- A chunk about a related but different topic is NOT relevant.
- A chunk that provides necessary background or definitions for understanding the answer IS relevant.
- Output ONLY valid JSON. No other text."""

CONTEXT_RELEVANCE_USER = """Question: {question}

Chunk (ID: {chunk_id}):
{chunk_text}

Does this chunk contain information relevant to answering the question? Respond with JSON:
{{"relevant": true or false, "reason": "brief explanation"}}"""


def judge_chunk_relevance(question: str, chunk_id: str, chunk_text: str) -> dict:
    from llm_provider import call_llm_raw

    result = call_llm_raw(
        system_prompt=CONTEXT_RELEVANCE_SYSTEM,
        user_message=CONTEXT_RELEVANCE_USER.format(
            question=question, chunk_id=chunk_id, chunk_text=chunk_text[:1000]),
        temperature=0,
        max_tokens=256,
    )

    parsed = _parse_json(result["text"])
    if isinstance(parsed, dict):
        return {
            "relevant": bool(parsed.get("relevant", False)),
            "reason": str(parsed.get("reason", "")),
        }

    return {"relevant": False, "reason": "Failed to parse judge response"}


# ---------------------------------------------------------------------------
# Evaluate Relevance (both answer + context) for a run
# ---------------------------------------------------------------------------

def evaluate_relevance(run_id: str) -> dict:
    from eval.runner import RUNS_DIR
    from llm_provider import get_llm_provider, get_model_name

    run_dir = RUNS_DIR / run_id
    answers_path = run_dir / "answers.json"
    relevance_path = run_dir / "relevance.json"

    if not answers_path.exists():
        raise FileNotFoundError(f"No answers.json for run {run_id}")

    answers = json.loads(answers_path.read_text(encoding="utf-8"))

    answer_relevance_results = []
    context_relevance_results = []
    total_answer_relevant = 0
    total_answers_judged = 0
    total_chunks_relevant = 0
    total_chunks_judged = 0

    for ans in answers:
        question_id = ans["question_id"]
        answer_text = ans.get("answer_text", "")
        question = ans.get("question", "") or ""
        chunks = ans.get("retrieved_chunks", [])

        if not question:
            if not hasattr(evaluate_relevance, '_q_map'):
                from eval.runner import load_dataset
                evaluate_relevance._q_map = {q.question_id: q.question for q in load_dataset()}
            question = evaluate_relevance._q_map.get(question_id, "")

        if not answer_text:
            continue

        logger.info(f"Relevance: evaluating answer for question {question_id}")

        # Answer relevance
        ar_verdict = judge_answer_relevance(question, answer_text)
        answer_relevance_results.append({
            "question_id": question_id,
            "answer_id": ans["answer_id"],
            "is_refusal": ans.get("is_refusal", False),
            "relevant": ar_verdict["relevant"],
            "reason": ar_verdict["reason"],
        })
        total_answers_judged += 1
        if ar_verdict["relevant"]:
            total_answer_relevant += 1

        # Context relevance — judge each chunk
        chunk_verdicts = []
        for chunk in chunks:
            cid = chunk.get("chunk_id", "unknown")
            ctext = chunk.get("text", "")
            if not ctext:
                continue
            cr_verdict = judge_chunk_relevance(question, cid, ctext)
            chunk_verdicts.append({
                "chunk_id": cid,
                "relevant": cr_verdict["relevant"],
                "reason": cr_verdict["reason"],
            })
            total_chunks_judged += 1
            if cr_verdict["relevant"]:
                total_chunks_relevant += 1

        context_relevance_results.append({
            "question_id": question_id,
            "answer_id": ans["answer_id"],
            "chunks": chunk_verdicts,
            "context_relevance": (sum(1 for c in chunk_verdicts if c["relevant"]) /
                                  len(chunk_verdicts)) if chunk_verdicts else 0.0,
        })

    result = {
        "run_id": run_id,
        "answer_relevance_prompt_version": ANSWER_RELEVANCE_PROMPT_VERSION,
        "context_relevance_prompt_version": CONTEXT_RELEVANCE_PROMPT_VERSION,
        "judge_model": get_model_name(),
        "judge_provider": get_llm_provider(),
        "judge_temperature": 0,
        "answer_relevance": answer_relevance_results,
        "context_relevance": context_relevance_results,
    }

    with open(relevance_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str)

    avg_answer_relevance = (total_answer_relevant / total_answers_judged
                            if total_answers_judged else None)
    avg_context_relevance = (total_chunks_relevant / total_chunks_judged
                             if total_chunks_judged else None)

    # Per-question context relevance average
    cq_scores = [r["context_relevance"] for r in context_relevance_results
                 if r["chunks"]]
    avg_context_per_question = (sum(cq_scores) / len(cq_scores)
                                if cq_scores else None)

    return {
        "answer_relevance": round(avg_answer_relevance, 4) if avg_answer_relevance is not None else None,
        "context_relevance": round(avg_context_per_question, 4) if avg_context_per_question is not None else None,
        "n_answers": total_answers_judged,
        "n_chunks": total_chunks_judged,
        "answer_relevance_prompt_version": ANSWER_RELEVANCE_PROMPT_VERSION,
        "context_relevance_prompt_version": CONTEXT_RELEVANCE_PROMPT_VERSION,
    }
