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
_CLAUSE_COMMA_RE = re.compile(
    r',\s+(?=(?:who|which|where|since|from|specializing|working|serving|'
    r'based|located|including|leading|managing|focusing|holding|currently|'
    r'previously|formerly|responsible)\b)',
    re.IGNORECASE,
)
_AND_CLAUSE_RE = re.compile(
    r',?\s+and\s+(?=[A-Z]|(?:it|they|he|she|this|these|the|its|their|his|her)\s)',
    re.IGNORECASE,
)


def _tokenize(text: str) -> set[str]:
    return {w.lower() for w in _WORD_RE.findall(text) if len(w) > 2 and w.lower() not in STOPWORDS}


def _decompose_sentence(sentence: str) -> list[str]:
    """Break a compound sentence into atomic sub-claims."""
    citations = _CITATION_RE.findall(sentence)
    cite_suffix = " " + " ".join(f"[{c}]" for c in citations) if citations else ""
    bare = _CITATION_RE.sub("", sentence).strip().rstrip(".")
    bare = re.sub(r'\s+,', ',', bare)
    bare = re.sub(r'\s{2,}', ' ', bare)

    parts = [s.strip() for s in bare.split(";") if s.strip()]

    refined = []
    for part in parts:
        subs = _AND_CLAUSE_RE.split(part)
        if len(subs) > 1 and all(len(s.split()) >= 3 for s in subs):
            refined.extend(s.strip() for s in subs if s.strip())
        else:
            refined.append(part)

    final = []
    for part in refined:
        comma_parts = _CLAUSE_COMMA_RE.split(part)
        if len(comma_parts) > 1:
            final.extend(p.strip() for p in comma_parts if p.strip())
        else:
            final.append(part)

    return [(f + cite_suffix).strip() for f in final if f.strip()] or [sentence]


def _split_claims(answer: str) -> list[str]:
    """Split answer into atomic claims (one fact per claim)."""
    sentences = []
    for line in answer.split('\n'):
        line = line.strip()
        if not line:
            continue
        bullet = _BULLET_RE.match(line)
        if bullet:
            claim = line[bullet.end():].strip()
            if claim:
                sentences.append(claim)
        else:
            for sent in _SENTENCE_RE.split(line):
                sent = sent.strip()
                if sent:
                    sentences.append(sent)
    if not sentences:
        sentences = [answer.strip()]

    claims = []
    for sent in sentences:
        claims.extend(_decompose_sentence(sent))
    return claims


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
            "text": claim[:200],
            "grounded": is_grounded,
            "overlap_ratio": round(len(overlap) / len(claim_tokens), 2) if claim_tokens else 1.0,
            "citations": sorted(claim_citations) if claim_citations else [],
        })

    score = grounded / len(claims) if claims else 0.0

    return {
        "score": round(score, 2),
        "grounded_claims": grounded,
        "total_claims": len(claims),
        "claims": claim_results,
        "invalid_citations": invalid_citations,
    }
