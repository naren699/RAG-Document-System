from rank_bm25 import BM25Okapi
import logging
import re

logger = logging.getLogger(__name__)

_index = None
_chunks = None


def _tokenize(text: str) -> list[str]:
    text = text.lower()
    tokens = re.findall(r'\b\w+\b', text)
    return tokens


def build_index(chunks: list[dict]):
    global _index, _chunks
    _chunks = chunks
    if not chunks:
        _index = None
        logger.info("BM25 index cleared (no chunks)")
        return
    tokenized = [_tokenize(c["text"]) for c in chunks]
    _index = BM25Okapi(tokenized)
    logger.info(f"Built BM25 index with {len(chunks)} chunks")


def get_index_and_chunks():
    return _index, _chunks


def query_bm25(query: str, k: int = 5, doc_id: str = None) -> list[dict]:
    if _index is None or _chunks is None:
        logger.warning("BM25 index not built yet")
        return []

    tokenized_query = _tokenize(query)
    scores = _index.get_scores(tokenized_query)

    scored_chunks = []
    for i, score in enumerate(scores):
        chunk = _chunks[i]
        if doc_id and chunk.get("doc_id") != doc_id:
            continue
        scored_chunks.append({
            "chunk_id": chunk["chunk_id"],
            "text": chunk["text"],
            "doc_id": chunk["doc_id"],
            "page_num": chunk["page_num"],
            "source": chunk["source"],
            "token_count": chunk["token_count"],
            "score": round(float(score), 4),
        })

    scored_chunks.sort(key=lambda x: x["score"], reverse=True)
    return scored_chunks[:k]


def rebuild_from_chromadb():
    """Rebuild BM25 index from ChromaDB data (called on startup)."""
    from vector_store import get_collection

    collection = get_collection()
    if collection.count() == 0:
        logger.info("ChromaDB is empty, skipping BM25 index build")
        return

    data = collection.get(include=["documents", "metadatas"])
    chunks = []
    for i in range(len(data["ids"])):
        chunks.append({
            "chunk_id": data["ids"][i],
            "text": data["documents"][i],
            "doc_id": data["metadatas"][i]["doc_id"],
            "page_num": data["metadatas"][i]["page_num"],
            "source": data["metadatas"][i]["source"],
            "token_count": data["metadatas"][i]["token_count"],
        })

    build_index(chunks)
