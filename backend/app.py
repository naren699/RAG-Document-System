import logging
import os
import time
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("fare.log"),
    ],
)
logger = logging.getLogger("fare")

app = FastAPI(title="FARE", description="Faithful Abstaining RAG Evaluator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://localhost:5175"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
PAGE_IMAGES_DIR = Path("page_images")
PAGE_IMAGES_DIR.mkdir(exist_ok=True)
MAX_FILE_SIZE = 50 * 1024 * 1024

app.mount("/page_images", StaticFiles(directory="page_images"), name="page_images")

COLPALI_ENABLED = os.getenv("COLPALI_ENABLED", "false").lower() == "true"


class QueryRequest(BaseModel):
    query: str
    k: int = 5
    method: str = "hybrid"
    doc_id: str | None = None


@app.on_event("startup")
def startup():
    from bm25_retriever import rebuild_from_chromadb
    from llm_provider import get_llm_provider
    logger.info("Starting FARE backend...")
    logger.info(f"LLM provider: {get_llm_provider()}")
    logger.info(f"ColPali enabled: {COLPALI_ENABLED}")
    rebuild_from_chromadb()
    logger.info("FARE backend ready")


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/api/ingest")
async def ingest_pdf(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File exceeds 50MB limit")

    doc_id = Path(file.filename).stem
    save_path = UPLOAD_DIR / f"{doc_id}_{uuid.uuid4().hex[:8]}.pdf"
    save_path.write_bytes(contents)

    logger.info(f"Ingesting PDF: {file.filename} as {doc_id}")

    try:
        from page_classifier import classify_pages
        from pdf_extractor import extract_text_from_pdf
        from chunker import chunk_document
        from embedder import embed_texts
        from vector_store import add_chunks
        from bm25_retriever import build_index, get_index_and_chunks

        classification = classify_pages(str(save_path))
        text_pages_info = [p for p in classification if p["page_type"] == "text"]
        visual_pages_info = [p for p in classification if p["page_type"] == "visual"]

        pages = extract_text_from_pdf(str(save_path))

        text_page_nums = {p["page_num"] for p in text_pages_info}
        text_pages = [p for p in pages if p["page_num"] in text_page_nums]
        text_chunks = chunk_document(text_pages, doc_id)

        all_chunks = []
        all_embeddings = []

        if text_chunks:
            texts = [c["text"] for c in text_chunks]
            text_embeddings = embed_texts(texts)
            for chunk in text_chunks:
                chunk["page_type"] = "text"
            all_chunks.extend(text_chunks)
            all_embeddings.extend(text_embeddings)

        visual_chunk_count = 0
        if COLPALI_ENABLED and visual_pages_info:
            from colpali_processor import process_visual_pages
            visual_chunks, visual_embeddings = process_visual_pages(
                str(save_path), visual_pages_info, doc_id
            )
            all_chunks.extend(visual_chunks)
            all_embeddings.extend(visual_embeddings)
            visual_chunk_count = len(visual_chunks)
        elif visual_pages_info:
            visual_page_nums = {p["page_num"] for p in visual_pages_info}
            visual_text_pages = [p for p in pages if p["page_num"] in visual_page_nums and p["has_text"]]
            if visual_text_pages:
                visual_as_text = chunk_document(visual_text_pages, doc_id)
                for chunk in visual_as_text:
                    chunk["page_type"] = "visual_fallback"
                if visual_as_text:
                    vt_texts = [c["text"] for c in visual_as_text]
                    vt_embeddings = embed_texts(vt_texts)
                    all_chunks.extend(visual_as_text)
                    all_embeddings.extend(vt_embeddings)

        if not all_chunks:
            raise HTTPException(status_code=400, detail="No content could be extracted from the PDF")

        add_chunks(all_chunks, all_embeddings)

        _, existing_chunks = get_index_and_chunks()
        bm25_chunks = (existing_chunks or []) + [c for c in all_chunks if c.get("page_type") != "visual"]
        build_index(bm25_chunks)

        logger.info(
            f"Ingestion complete: {doc_id}, "
            f"{len(text_chunks)} text chunks, {visual_chunk_count} visual chunks"
        )

        return {
            "status": "success",
            "doc_id": doc_id,
            "chunks_count": len(all_chunks),
            "text_chunks": len(text_chunks),
            "visual_chunks": visual_chunk_count,
            "total_pages": len(pages),
            "text_pages": len(text_pages_info),
            "visual_pages": len(visual_pages_info),
            "classification": classification,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ingestion failed for {file.filename}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        save_path.unlink(missing_ok=True)


@app.post("/api/retrieve")
def retrieve_chunks(req: QueryRequest):
    from retriever import retrieve_hybrid, retrieve_dense_only, retrieve_bm25_only

    logger.info(f"Retrieve: '{req.query}' | method={req.method} k={req.k}")

    if req.method == "hybrid":
        chunks = retrieve_hybrid(req.query, k=req.k, doc_id=req.doc_id)
    elif req.method == "dense":
        chunks = retrieve_dense_only(req.query, k=req.k, doc_id=req.doc_id)
    elif req.method == "bm25":
        chunks = retrieve_bm25_only(req.query, k=req.k, doc_id=req.doc_id)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown method: {req.method}")

    return {"query": req.query, "method": req.method, "chunks": chunks}


def _do_retrieval(query: str, k: int, method: str, doc_id: str | None) -> tuple[list[dict], int]:
    """Perform retrieval and return (chunks, elapsed_ms)."""
    from retriever import retrieve_hybrid, retrieve_dense_only, retrieve_bm25_only

    start = time.time()
    if method == "hybrid":
        chunks = retrieve_hybrid(query, k=k, doc_id=doc_id)
    elif method == "dense":
        chunks = retrieve_dense_only(query, k=k, doc_id=doc_id)
    elif method == "bm25":
        chunks = retrieve_bm25_only(query, k=k, doc_id=doc_id)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown method: {method}")
    elapsed = int((time.time() - start) * 1000)
    return chunks, elapsed


@app.post("/api/query")
def query_document(req: QueryRequest):
    """Full RAG pipeline: retrieve → LLM generates answer → return with sources and timings."""
    from llm_provider import generate_answer
    from vector_store import get_stats

    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    if len(req.query) > 500:
        raise HTTPException(status_code=400, detail="Query too long (max 500 characters)")

    stats = get_stats()
    if stats["total_chunks"] == 0:
        raise HTTPException(status_code=400, detail="No documents uploaded. Please ingest a PDF first.")

    total_start = time.time()
    logger.info(f"Query: '{req.query}' | method={req.method} k={req.k}")

    chunks, retrieval_ms = _do_retrieval(req.query, req.k, req.method, req.doc_id)

    try:
        result = generate_answer(req.query, chunks)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=429, detail=str(e))

    total_ms = int((time.time() - total_start) * 1000)

    logger.info(
        f"Query complete: retrieval={retrieval_ms}ms, "
        f"generation={result.get('generation_time_ms', 0)}ms, total={total_ms}ms"
    )

    return {
        "query": req.query,
        "answer": result["answer"],
        "sources": chunks,
        "provider": result.get("provider", "unknown"),
        "model": result.get("model", "unknown"),
        "tokens_used": {
            "input_tokens": result.get("input_tokens", 0),
            "output_tokens": result.get("output_tokens", 0),
        },
        "timings": {
            "retrieval_ms": retrieval_ms,
            "generation_ms": result.get("generation_time_ms", 0),
            "total_ms": total_ms,
        },
    }


@app.get("/api/documents")
def list_documents():
    from vector_store import list_documents as vl
    docs = vl()
    return {"documents": docs}


@app.delete("/api/clear")
def clear_database():
    from vector_store import clear_all
    from bm25_retriever import build_index
    clear_all()
    build_index([])
    logger.info("Database cleared")
    return {"status": "cleared"}


@app.get("/api/debug")
def debug_info():
    from vector_store import get_stats
    from embedder import MODEL_NAME
    from chunker import CHUNK_SIZE, CHUNK_OVERLAP
    from llm_provider import get_llm_provider, GEMINI_MODEL, CLAUDE_MODEL

    stats = get_stats()
    provider = get_llm_provider()
    return {
        "llm_provider": provider,
        "llm_model": GEMINI_MODEL if provider == "gemini" else CLAUDE_MODEL,
        "embedding_model": MODEL_NAME,
        "chunk_size": CHUNK_SIZE,
        "chunk_overlap": CHUNK_OVERLAP,
        "colpali_enabled": COLPALI_ENABLED,
        **stats,
    }


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
