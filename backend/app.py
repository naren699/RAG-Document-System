import json
import logging
import os
import time
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
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
    score_threshold: float | None = None
    history: list[dict] | None = None
    mask_pii: bool = False


@app.on_event("startup")
def startup():
    from bm25_retriever import rebuild_from_chromadb
    from llm_provider import get_llm_provider
    logger.info("Starting FARE backend...")
    logger.info(f"LLM provider: {get_llm_provider()}")
    logger.info(f"ColPali enabled: {COLPALI_ENABLED}")
    if COLPALI_ENABLED:
        import torch
        if not torch.cuda.is_available():
            logger.warning("ColPali enabled but no GPU detected — visual page processing will be slow (30-60s per page)")
    rebuild_from_chromadb()
    logger.info("FARE backend ready")


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/api/ingest")
async def ingest_pdf(file: UploadFile = File(...), exclude_pages: str = Form("")):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File exceeds 50MB limit")

    excluded = set()
    if exclude_pages.strip():
        try:
            excluded = {int(p.strip()) for p in exclude_pages.split(",") if p.strip()}
        except ValueError:
            raise HTTPException(status_code=400, detail="exclude_pages must be comma-separated page numbers")

    doc_id = Path(file.filename).stem
    save_path = UPLOAD_DIR / f"{doc_id}_{uuid.uuid4().hex[:8]}.pdf"
    save_path.write_bytes(contents)

    logger.info(f"Ingesting PDF: {file.filename} as {doc_id}")

    MAX_PAGES = 200
    try:
        from page_classifier import classify_pages
        from pdf_extractor import extract_text_from_pdf
        from chunker import chunk_document
        from embedder import embed_texts
        from vector_store import add_chunks
        from bm25_retriever import rebuild_from_chromadb

        try:
            classification = classify_pages(str(save_path))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        if len(classification) > MAX_PAGES:
            raise HTTPException(status_code=400, detail=f"PDF has {len(classification)} pages (max {MAX_PAGES})")
        if excluded:
            classification = [p for p in classification if p["page_num"] not in excluded]
        text_pages_info = [p for p in classification if p["page_type"] == "text"]
        visual_pages_info = [p for p in classification if p["page_type"] == "visual"]

        try:
            pages = extract_text_from_pdf(str(save_path))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        if excluded:
            pages = [p for p in pages if p["page_num"] not in excluded]

        warnings = []

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
        visual_results = None
        if COLPALI_ENABLED and visual_pages_info:
            from colpali_processor import process_visual_pages
            from vector_store import add_visual_chunks
            visual_chunks, visual_embeddings = process_visual_pages(
                str(save_path), visual_pages_info, doc_id
            )
            if visual_chunks:
                add_visual_chunks(visual_chunks, visual_embeddings)
            visual_chunk_count = len(visual_chunks)
        elif visual_pages_info:
            from image_extractor import extract_visual_pages
            visual_results = extract_visual_pages(
                pdf_path=str(save_path),
                visual_pages=visual_pages_info,
                doc_id=doc_id,
            )
            if visual_results["chunks"]:
                v_texts = [c["text"] for c in visual_results["chunks"]]
                v_embeddings = embed_texts(v_texts)
                all_chunks.extend(visual_results["chunks"])
                all_embeddings.extend(v_embeddings)
                visual_chunk_count = len(visual_results["chunks"])
            if visual_results.get("warnings"):
                warnings.extend(visual_results["warnings"])

        if not all_chunks:
            if visual_pages_info:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"This PDF has {len(visual_pages_info)} image-based page(s) "
                        f"but no extractable text. Visual page images were saved. "
                        f"Install OCR support or enable vision LLM to extract text from images."
                    ),
                )
            raise HTTPException(status_code=400, detail="No content could be extracted from the PDF")

        add_chunks(all_chunks, all_embeddings)

        rebuild_from_chromadb()

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
            "excluded_pages": sorted(excluded) if excluded else [],
            "warnings": warnings,
            "classification": classification,
            "ocr_pages": visual_results["ocr_page_count"] if visual_results else 0,
            "vision_pages": visual_results["vision_page_count"] if visual_results else 0,
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
    threshold = req.score_threshold

    if req.method == "hybrid":
        chunks, timings = retrieve_hybrid(req.query, k=req.k, doc_id=req.doc_id, score_threshold=threshold)
    elif req.method == "dense":
        chunks, timings = retrieve_dense_only(req.query, k=req.k, doc_id=req.doc_id, score_threshold=threshold)
    elif req.method == "bm25":
        chunks, timings = retrieve_bm25_only(req.query, k=req.k, doc_id=req.doc_id, score_threshold=threshold)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown method: {req.method}")

    return {"query": req.query, "method": req.method, "chunks": chunks, "timings": timings}


def _do_retrieval(query: str, k: int, method: str, doc_id: str | None,
                  score_threshold: float | None = None) -> tuple[list[dict], dict]:
    """Perform retrieval and return (chunks, detailed_timings)."""
    from retriever import retrieve_hybrid, retrieve_dense_only, retrieve_bm25_only

    start = time.time()
    if method == "hybrid":
        chunks, timings = retrieve_hybrid(query, k=k, doc_id=doc_id, score_threshold=score_threshold)
    elif method == "dense":
        chunks, timings = retrieve_dense_only(query, k=k, doc_id=doc_id, score_threshold=score_threshold)
    elif method == "bm25":
        chunks, timings = retrieve_bm25_only(query, k=k, doc_id=doc_id, score_threshold=score_threshold)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown method: {method}")
    timings["retrieval_total_ms"] = int((time.time() - start) * 1000)
    return chunks, timings


@app.post("/api/query")
def query_document(req: QueryRequest):
    """Full RAG pipeline: retrieve → rerank → LLM generates answer → return with sources and timings."""
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
    threshold = req.score_threshold
    logger.info(f"Query: '{req.query}' | method={req.method} k={req.k} threshold={threshold}")

    chunks, retrieval_timings = _do_retrieval(req.query, req.k, req.method, req.doc_id, threshold)

    if not chunks:
        total_ms = int((time.time() - total_start) * 1000)
        logger.info(f"No relevant chunks found (threshold={threshold}), returning not-found")
        return {
            "query": req.query,
            "answer": "I couldn't find this in the uploaded documents.",
            "sources": [],
            "is_not_found": True,
            "provider": "none",
            "model": "none",
            "tokens_used": {"input_tokens": 0, "output_tokens": 0},
            "timings": {**retrieval_timings, "generation_ms": 0, "total_ms": total_ms},
        }

    try:
        result = generate_answer(req.query, chunks)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=429, detail=str(e))

    total_ms = int((time.time() - total_start) * 1000)
    retrieval_total = retrieval_timings.get("retrieval_total_ms", 0)

    logger.info(
        f"Query complete: retrieval={retrieval_total}ms, "
        f"generation={result.get('generation_time_ms', 0)}ms, total={total_ms}ms"
    )

    from grounding import compute_grounding_score
    grounding = compute_grounding_score(result["answer"], chunks)

    return {
        "query": req.query,
        "answer": result["answer"],
        "sources": chunks,
        "is_not_found": False,
        "provider": result.get("provider", "unknown"),
        "model": result.get("model", "unknown"),
        "tokens_used": {
            "input_tokens": result.get("input_tokens", 0),
            "output_tokens": result.get("output_tokens", 0),
        },
        "grounding": grounding,
        "timings": {
            **retrieval_timings,
            "generation_ms": result.get("generation_time_ms", 0),
            "total_ms": total_ms,
        },
        "estimated_cost_usd": result.get("estimated_cost_usd"),
    }


@app.post("/api/query/stream")
async def query_document_stream(req: QueryRequest):
    """Streaming RAG pipeline: retrieve → rerank → stream LLM tokens via SSE."""
    from llm_provider import stream_llm, format_context, get_llm_provider, get_model_name, _estimate_cost, rewrite_follow_up
    from vector_store import get_stats

    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    if len(req.query) > 500:
        raise HTTPException(status_code=400, detail="Query too long (max 500 characters)")

    stats = get_stats()
    if stats["total_chunks"] == 0:
        raise HTTPException(status_code=400, detail="No documents uploaded. Please ingest a PDF first.")

    threshold = req.score_threshold

    effective_query = req.query
    if req.history and len(req.history) >= 2:
        effective_query = rewrite_follow_up(req.query, req.history)
        logger.info(f"Rewritten query: '{req.query}' → '{effective_query}'")

    def event_stream():
        total_start = time.time()

        if effective_query != req.query:
            yield f"event: rewritten_query\ndata: {json.dumps(effective_query)}\n\n"

        chunks, retrieval_timings = _do_retrieval(effective_query, req.k, req.method, req.doc_id, threshold)

        # Send sources immediately
        source_data = []
        for c in chunks:
            source_data.append({
                "chunk_id": c.get("chunk_id"),
                "text": c.get("text"),
                "page_num": c.get("page_num"),
                "doc_id": c.get("doc_id"),
                "source": c.get("source"),
                "score": c.get("score"),
                "token_count": c.get("token_count"),
                "page_type": c.get("page_type", "text"),
                "section_title": c.get("section_title"),
                "image_path": c.get("image_path"),
                "extraction_method": c.get("extraction_method"),
                "confidence": c.get("confidence"),
                "dense_score": c.get("dense_score"),
                "bm25_score": c.get("bm25_score"),
                "rerank_score": c.get("rerank_score"),
                "rrf_score": c.get("rrf_score"),
            })
        yield f"event: sources\ndata: {json.dumps(source_data)}\n\n"

        if not chunks:
            done_data = {
                "answer": "I couldn't find this in the uploaded documents.",
                "is_not_found": True,
                "provider": "none",
                "model": "none",
                "tokens_used": {"input_tokens": 0, "output_tokens": 0},
                "timings": {**retrieval_timings, "generation_ms": 0, "total_ms": int((time.time() - total_start) * 1000)},
            }
            yield f"event: done\ndata: {json.dumps(done_data)}\n\n"
            return

        context = format_context(chunks, mask=req.mask_pii)
        provider = get_llm_provider()
        model = get_model_name()
        gen_start = time.time()
        ttft = None
        full_answer = []

        usage = {"input_tokens": 0, "output_tokens": 0}
        try:
            for item in stream_llm(context, req.query, req.history):
                if isinstance(item, dict) and item.get("__usage__"):
                    usage = item
                    continue
                if ttft is None:
                    ttft = int((time.time() - gen_start) * 1000)
                full_answer.append(item)
                yield f"event: token\ndata: {json.dumps(item)}\n\n"
        except Exception as e:
            logger.error(f"Streaming error: {e}", exc_info=True)
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
            return

        from grounding import compute_grounding_score

        gen_ms = int((time.time() - gen_start) * 1000)
        total_ms = int((time.time() - total_start) * 1000)
        answer_text = "".join(full_answer)
        in_tokens = usage.get("input_tokens", 0)
        out_tokens = usage.get("output_tokens", 0)
        tokens_estimated = usage.get("estimated", False)

        grounding = compute_grounding_score(answer_text, chunks)

        done_data = {
            "answer": answer_text,
            "is_not_found": False,
            "provider": provider,
            "model": model,
            "tokens_used": {"input_tokens": in_tokens, "output_tokens": out_tokens, "estimated": tokens_estimated},
            "grounding": grounding,
            "timings": {
                **retrieval_timings,
                "generation_ms": gen_ms,
                "time_to_first_token_ms": ttft,
                "total_ms": total_ms,
            },
            "estimated_cost_usd": _estimate_cost(model, in_tokens, out_tokens),
        }
        yield f"event: done\ndata: {json.dumps(done_data)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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


@app.post("/api/debug/retrieve")
def debug_retrieve(req: QueryRequest):
    """Run all three retrieval methods side-by-side for diagnostic comparison."""
    from retriever import retrieve_hybrid, retrieve_dense_only, retrieve_bm25_only

    threshold = req.score_threshold
    results = {}
    for method, fn in [("dense", retrieve_dense_only), ("bm25", retrieve_bm25_only), ("hybrid", retrieve_hybrid)]:
        start = time.time()
        chunks, timings = fn(req.query, k=req.k, doc_id=req.doc_id, score_threshold=threshold)
        elapsed = int((time.time() - start) * 1000)
        results[method] = {"chunks": chunks, "time_ms": elapsed, "timings": timings}

    return {"query": req.query, **results}


@app.get("/api/documents/{doc_id}/chunks")
def get_document_chunks(doc_id: str):
    """List all chunks for a specific document."""
    from vector_store import get_collection

    collection = get_collection()
    data = collection.get(where={"doc_id": doc_id}, include=["documents", "metadatas"])

    if not data["ids"]:
        raise HTTPException(status_code=404, detail=f"No document found with id: {doc_id}")

    chunks = []
    for i in range(len(data["ids"])):
        meta = data["metadatas"][i]
        chunks.append({
            "chunk_id": data["ids"][i],
            "text": data["documents"][i],
            "page_num": meta["page_num"],
            "token_count": meta["token_count"],
            "page_type": meta.get("page_type", "text"),
            "section_title": meta.get("section_title"),
            "extraction_method": meta.get("extraction_method"),
            "confidence": meta.get("confidence"),
            "image_path": meta.get("image_path"),
        })

    chunks.sort(key=lambda c: (c["page_num"], c["chunk_id"]))
    return {"doc_id": doc_id, "total_chunks": len(chunks), "chunks": chunks}


@app.delete("/api/documents/{doc_id}")
def delete_document(doc_id: str):
    """Delete a single document and all its chunks."""
    from vector_store import delete_by_doc_id
    from bm25_retriever import rebuild_from_chromadb

    deleted_count = delete_by_doc_id(doc_id)
    if deleted_count == 0:
        raise HTTPException(status_code=404, detail=f"No document found with id: {doc_id}")

    rebuild_from_chromadb()
    logger.info(f"Deleted document {doc_id} ({deleted_count} chunks)")
    return {"status": "deleted", "doc_id": doc_id, "chunks_deleted": deleted_count}


class RechunkRequest(BaseModel):
    chunk_size: int = 300
    chunk_overlap: int = 50


@app.post("/api/documents/{doc_id}/rechunk")
def rechunk_document(doc_id: str, req: RechunkRequest):
    """Re-chunk an existing document with new chunk_size and chunk_overlap settings."""
    from vector_store import get_chunks_by_doc, delete_by_doc_id, add_chunks
    from chunker import chunk_document, count_tokens
    from embedder import embed_texts
    from bm25_retriever import rebuild_from_chromadb

    existing = get_chunks_by_doc(doc_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"No document found with id: {doc_id}")

    pages = {}
    for c in existing:
        pn = c.get("page_num", 1)
        if pn not in pages:
            pages[pn] = []
        pages[pn].append(c["text"])

    page_list = []
    for pn in sorted(pages.keys()):
        text = "\n\n".join(pages[pn])
        page_list.append({"page_num": pn, "text": text, "has_text": bool(text.strip())})

    delete_by_doc_id(doc_id)

    new_chunks = chunk_document(page_list, doc_id, chunk_size=req.chunk_size, chunk_overlap=req.chunk_overlap)
    if new_chunks:
        texts = [c["text"] for c in new_chunks]
        embeddings = embed_texts(texts)
        add_chunks(new_chunks, embeddings)

    rebuild_from_chromadb()
    logger.info(f"Re-chunked {doc_id}: {len(existing)} → {len(new_chunks)} chunks (size={req.chunk_size}, overlap={req.chunk_overlap})")
    return {
        "doc_id": doc_id,
        "old_chunks": len(existing),
        "new_chunks": len(new_chunks),
        "chunk_size": req.chunk_size,
        "chunk_overlap": req.chunk_overlap,
    }


@app.post("/api/feedback")
def submit_feedback(body: dict):
    """Log user feedback (thumbs up/down) on an answer."""
    import datetime
    feedback_path = Path("feedback.jsonl")
    entry = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "query": body.get("query", ""),
        "answer": body.get("answer", "")[:500],
        "rating": body.get("rating", ""),
    }
    with open(feedback_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    logger.info(f"Feedback: {entry['rating']} for query '{entry['query'][:50]}'")
    return {"status": "recorded"}


@app.post("/api/eval/quick")
def run_quick_eval():
    """Run 4 quick test queries and return pass/fail results."""
    from llm_provider import generate_answer

    test_cases = [
        {
            "query": "What are the priority levels in support tickets?",
            "expected_keywords": ["P1", "P2", "P3"],
            "expected_page": 2,
            "should_find": True,
        },
        {
            "query": "How many days of paid annual leave do full-time employees receive?",
            "expected_keywords": ["18"],
            "expected_page": 3,
            "should_find": True,
        },
        {
            "query": "What should happen if the production error rate exceeds 3% for five consecutive minutes?",
            "expected_keywords": ["pause", "rollback"],
            "expected_page": 2,
            "should_find": True,
        },
        {
            "query": "What is the CEO's annual salary?",
            "expected_keywords": [],
            "expected_page": None,
            "should_find": False,
        },
        {
            "query": "What is the recipe for chocolate cake?",
            "expected_keywords": [],
            "expected_page": None,
            "should_find": False,
        },
        {
            "query": "What is the CEO's phone number?",
            "expected_keywords": [],
            "expected_page": None,
            "should_find": False,
        },
        {
            "query": "Who won the 2024 World Cup?",
            "expected_keywords": [],
            "expected_page": None,
            "should_find": False,
        },
    ]

    results = []
    for tc in test_cases:
        start = time.time()
        try:
            chunks, retrieval_timings = _do_retrieval(tc["query"], k=5, method="hybrid", doc_id=None)
            llm_result = generate_answer(tc["query"], chunks) if chunks else {
                "answer": "I couldn't find this in the uploaded documents."
            }
            latency_ms = int((time.time() - start) * 1000)
            answer = llm_result.get("answer", "")

            not_found_phrases = [
                "i don't have that information",
                "i couldn't find",
                "not in the provided documents",
                "not in the uploaded documents",
                "no relevant information",
            ]
            answer_is_not_found = any(p in answer.lower() for p in not_found_phrases) or not chunks

            if tc["should_find"]:
                keywords_found = [kw for kw in tc["expected_keywords"] if kw.lower() in answer.lower()]
                passed = len(keywords_found) == len(tc["expected_keywords"]) and not answer_is_not_found
                page_hit = any(c.get("page_num") == tc["expected_page"] for c in chunks[:3]) if tc["expected_page"] else None
            else:
                passed = answer_is_not_found
                keywords_found = []
                page_hit = None

            from grounding import compute_grounding_score
            grounding = compute_grounding_score(answer, chunks) if chunks else {"score": 0.0}

            results.append({
                "query": tc["query"],
                "passed": passed,
                "should_find": tc["should_find"],
                "answer_snippet": answer[:200],
                "keywords_found": keywords_found,
                "keywords_expected": tc["expected_keywords"],
                "page_hit": page_hit,
                "num_chunks": len(chunks),
                "top_score": chunks[0]["score"] if chunks else 0,
                "faithfulness": grounding.get("score", 0.0),
                "latency_ms": latency_ms,
            })
        except Exception as e:
            results.append({
                "query": tc["query"],
                "passed": False,
                "error": str(e),
                "latency_ms": int((time.time() - start) * 1000),
            })

    passed_count = sum(1 for r in results if r.get("passed"))
    latencies = [r.get("latency_ms", 0) for r in results if "latency_ms" in r]
    avg_latency = int(sum(latencies) / len(latencies)) if latencies else 0
    max_latency = max(latencies) if latencies else 0
    faithfulness_scores = [r.get("faithfulness", 0) for r in results if r.get("should_find") and not r.get("error")]
    avg_faithfulness = round(sum(faithfulness_scores) / len(faithfulness_scores), 2) if faithfulness_scores else 0
    recall_hits = sum(1 for r in results if r.get("should_find") and r.get("page_hit"))
    recall_total = sum(1 for r in results if r.get("should_find") and r.get("keywords_expected"))
    recall_at_k = round(recall_hits / recall_total, 2) if recall_total else 0

    return {
        "total": len(results),
        "passed": passed_count,
        "failed": len(results) - passed_count,
        "pass_rate": round(passed_count / len(results) * 100, 1) if results else 0,
        "avg_faithfulness": avg_faithfulness,
        "recall_at_k": recall_at_k,
        "avg_latency_ms": avg_latency,
        "max_latency_ms": max_latency,
        "results": results,
    }


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
