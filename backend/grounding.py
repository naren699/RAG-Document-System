import re
import logging

logger = logging.getLogger(__name__)

STOPWORDS = {
    'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
    'what', 'which', 'who', 'whom', 'how', 'when', 'where', 'why',
    'do', 'does', 'did', 'in', 'on', 'at', 'of', 'to', 'for', 'with',
    'and', 'or', 'not', 'no', 'nor', 'this', 'that', 'it', 'its',
    'by', 'from', 'as', 'but', 'so', 'if', 'has', 'have', 'had',
    'can', 'could', 'would', 'should', 'will', 'shall', 'may', 'might', 'must',
    'about', 'into', 'through', 'during', 'before', 'after', 'above', 'below',
    'between', 'under', 'over', 'than', 'then', 'each', 'every',
    'all', 'any', 'some', 'such', 'also', 'they', 'them', 'their',
}

_SENTENCE_RE = re.compile(r'(?<=[.!?])\s+')
_BULLET_RE = re.compile(r'^[\s]*[*\-•]\s+')
_CITATION_RE = re.compile(r'\[(\d+)\]')
_WORD_RE = re.compile(r'[a-zA-Z0-9]+')


def _tokenize(text: str) -> set[str]:
    return {w.lower() for w in _WORD_RE.findall(text) if len(w) > 2 and w.lower() not in STOPWORDS}


def _split_claims(answer: str) -> list[str]:
    """Split answer into individual claims (sentences or bullet points)."""
    claims = []
    for line in answer.split('\n'):
        line = line.strip()
        if not line:
            continue
        bullet = _BULLET_RE.match(line)
        if bullet:
            claim = line[bullet.end():].strip()
            if claim:
                claims.append(claim)
        else:
            for sent in _SENTENCE_RE.split(line):
                sent = sent.strip()
                if sent:
                    claims.append(sent)
    return claims if claims else [answer.strip()]


def compute_grounding_score(answer: str, chunks: list[dict]) -> dict:
    """Check how well each claim in the answer is grounded in the retrieved chunks."""
    if not answer or not chunks:
        return {"score": 0.0, "grounded_claims": 0, "total_claims": 0, "claims": [], "invalid_citations": []}

    citations_in_answer = set(int(m) for m in _CITATION_RE.findall(answer))
    valid_indices = set(range(1, len(chunks) + 1))
    invalid_citations = sorted(citations_in_answer - valid_indices)

    all_chunk_tokens = set()
    chunk_tokens_by_idx = {}
    for i, c in enumerate(chunks):
        tokens = _tokenize(c.get("text", ""))
        chunk_tokens_by_idx[i + 1] = tokens
        all_chunk_tokens |= tokens

    claims = _split_claims(answer)
    grounded = 0
    claim_results = []

    for claim in claims:
        claim_tokens = _tokenize(claim)
        if not claim_tokens:
            grounded += 1
            claim_results.append({"text": claim[:120], "grounded": True})
            continue

        claim_citations = set(int(m) for m in _CITATION_RE.findall(claim))
        if claim_citations:
            cited_tokens = set()
            for idx in claim_citations:
                cited_tokens |= chunk_tokens_by_idx.get(idx, set())
            overlap = claim_tokens & cited_tokens
        else:
            overlap = claim_tokens & all_chunk_tokens

        is_grounded = len(overlap) >= len(claim_tokens) * 0.3
        if is_grounded:
            grounded += 1
        claim_results.append({
            "text": claim[:120],
            "grounded": is_grounded,
            "overlap_ratio": round(len(overlap) / len(claim_tokens), 2) if claim_tokens else 1.0,
        })

    score = grounded / len(claims) if claims else 0.0

    return {
        "score": round(score, 2),
        "grounded_claims": grounded,
        "total_claims": len(claims),
        "claims": claim_results,
        "invalid_citations": invalid_citations,
    }
