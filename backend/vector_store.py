import chromadb
import logging
import os

logger = logging.getLogger(__name__)

CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "./chroma_db")

_client = None
_collection = None


def get_collection():
    global _client, _collection
    if _collection is None:
        logger.info(f"Initializing ChromaDB at {CHROMA_DB_PATH}")
        _client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        _collection = _client.get_or_create_collection(
            name="documents",
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(f"ChromaDB ready. Collection has {_collection.count()} items.")
    return _collection


def add_chunks(chunks: list[dict], embeddings: list[list[float]]):
    collection = get_collection()

    ids = [c["chunk_id"] for c in chunks]
    documents = [c["text"] for c in chunks]
    metadatas = []
    for c in chunks:
        meta = {
            "doc_id": c["doc_id"],
            "page_num": c["page_num"],
            "source": c["source"],
            "token_count": c["token_count"],
            "page_type": c.get("page_type", "text"),
        }
        if c.get("image_path"):
            meta["image_path"] = c["image_path"]
        metadatas.append(meta)

    batch_size = 100
    for i in range(0, len(ids), batch_size):
        end = i + batch_size
        collection.add(
            ids=ids[i:end],
            embeddings=embeddings[i:end],
            documents=documents[i:end],
            metadatas=metadatas[i:end],
        )

    logger.info(f"Added {len(ids)} chunks to ChromaDB. Total: {collection.count()}")


def query_dense(query_embedding: list[float], k: int = 5, doc_id: str = None) -> list[dict]:
    collection = get_collection()

    where = {"doc_id": doc_id} if doc_id else None
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=k,
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    chunks = []
    for i in range(len(results["ids"][0])):
        score = 1 - results["distances"][0][i]
        chunks.append({
            "chunk_id": results["ids"][0][i],
            "text": results["documents"][0][i],
            "score": round(score, 4),
            **results["metadatas"][0][i],
        })

    return chunks


def list_documents() -> list[dict]:
    collection = get_collection()
    all_meta = collection.get(include=["metadatas"])

    doc_counts = {}
    for meta in all_meta["metadatas"]:
        did = meta["doc_id"]
        if did not in doc_counts:
            doc_counts[did] = 0
        doc_counts[did] += 1

    return [{"doc_id": did, "chunks_count": count} for did, count in doc_counts.items()]


def clear_all():
    global _collection, _client
    if _client is not None:
        _client.delete_collection("documents")
        _collection = None
        _collection = get_collection()
        logger.info("Cleared all documents from ChromaDB")


def get_stats() -> dict:
    collection = get_collection()
    count = collection.count()
    docs = list_documents()
    return {
        "total_chunks": count,
        "total_documents": len(docs),
        "documents": docs,
    }
