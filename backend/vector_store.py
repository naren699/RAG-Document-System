import chromadb
import logging
import os

logger = logging.getLogger(__name__)

CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "./chroma_db")

_client = None
_collection = None
_visual_collection = None


def get_collection() -> "chromadb.Collection":
    """Get or create the ChromaDB collection, initializing the client if needed."""
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


def add_chunks(chunks: list[dict], embeddings: list[list[float]]) -> None:
    """Store chunks and their embeddings in ChromaDB in batches of 100."""
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
        if c.get("section_title"):
            meta["section_title"] = c["section_title"]
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


def query_dense(query_embedding: list[float], k: int = 5, doc_id: str | None = None) -> list[dict]:
    """Find the k nearest chunks to query_embedding by cosine distance."""
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


def get_visual_collection() -> "chromadb.Collection":
    global _visual_collection, _client
    if _visual_collection is None:
        if _client is None:
            get_collection()
        _visual_collection = _client.get_or_create_collection(
            name="visual_pages",
            metadata={"hnsw:space": "cosine"},
        )
    return _visual_collection


def add_visual_chunks(chunks: list[dict], embeddings: list[list[float]]) -> None:
    collection = get_visual_collection()
    ids = [c["chunk_id"] for c in chunks]
    documents = [c["text"] for c in chunks]
    metadatas = []
    for c in chunks:
        meta = {
            "doc_id": c["doc_id"],
            "page_num": c["page_num"],
            "source": c["source"],
            "token_count": c.get("token_count", 0),
            "page_type": c.get("page_type", "visual"),
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
    logger.info(f"Added {len(ids)} visual chunks. Total: {collection.count()}")


def query_visual(query_embedding: list[float], k: int = 3, doc_id: str | None = None) -> list[dict]:
    collection = get_visual_collection()
    if collection.count() == 0:
        return []

    where = {"doc_id": doc_id} if doc_id else None
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(k, collection.count()),
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
    """Return a list of {doc_id, chunks_count} for all ingested documents."""
    collection = get_collection()
    all_meta = collection.get(include=["metadatas"])

    doc_counts = {}
    for meta in all_meta["metadatas"]:
        did = meta["doc_id"]
        if did not in doc_counts:
            doc_counts[did] = 0
        doc_counts[did] += 1

    return [{"doc_id": did, "chunks_count": count} for did, count in doc_counts.items()]


def delete_by_doc_id(doc_id: str) -> int:
    """Delete all chunks for a specific document. Returns count of deleted chunks."""
    collection = get_collection()
    existing = collection.get(where={"doc_id": doc_id})
    count = len(existing["ids"])
    if count > 0:
        collection.delete(where={"doc_id": doc_id})
        logger.info(f"Deleted {count} text chunks for doc_id={doc_id}")

    visual_col = get_visual_collection()
    if visual_col.count() > 0:
        v_existing = visual_col.get(where={"doc_id": doc_id})
        v_count = len(v_existing["ids"])
        if v_count > 0:
            visual_col.delete(where={"doc_id": doc_id})
            logger.info(f"Deleted {v_count} visual chunks for doc_id={doc_id}")
            count += v_count

    return count


def get_chunks_by_doc(doc_id: str) -> list[dict]:
    """Return all chunks for a document, sorted by chunk_id."""
    collection = get_collection()
    results = collection.get(where={"doc_id": doc_id}, include=["documents", "metadatas"])
    chunks = []
    for i, cid in enumerate(results["ids"]):
        meta = results["metadatas"][i]
        chunks.append({
            "chunk_id": cid,
            "text": results["documents"][i],
            "doc_id": meta.get("doc_id"),
            "page_num": meta.get("page_num"),
            "source": meta.get("source"),
            "token_count": meta.get("token_count"),
        })
    chunks.sort(key=lambda c: c["chunk_id"])
    return chunks


def clear_all() -> None:
    """Delete and recreate all ChromaDB collections."""
    global _collection, _visual_collection, _client
    if _client is not None:
        _client.delete_collection("documents")
        _collection = None
        _collection = get_collection()
        try:
            _client.delete_collection("visual_pages")
        except Exception:
            pass
        _visual_collection = None
        _visual_collection = get_visual_collection()
        logger.info("Cleared all documents from ChromaDB")


def get_stats() -> dict:
    """Return total_chunks, total_documents, and per-doc breakdown."""
    collection = get_collection()
    count = collection.count()
    docs = list_documents()
    return {
        "total_chunks": count,
        "total_documents": len(docs),
        "documents": docs,
    }
