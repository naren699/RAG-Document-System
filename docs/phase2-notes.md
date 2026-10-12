# Phase 2 Notes — Backend & Database

## Decisions Made

### Chunking
- **Size:** 500 tokens (configurable via `CHUNK_SIZE` env var)
- **Overlap:** 50 tokens (configurable via `CHUNK_OVERLAP` env var)
- **Why 500:** Large enough to preserve paragraph context, small enough for precise retrieval. A typical PDF page is ~250-400 tokens, so most pages become 1-2 chunks.
- **Why 50 overlap:** Prevents losing sentences that span chunk boundaries. ~10% overlap is a standard starting point.
- **Splitting strategy:** Prefers paragraph boundaries (`\n\n`). Falls back to sentence boundaries for long paragraphs. Never splits mid-sentence.
- **Tokenizer:** tiktoken `cl100k_base` — matches Claude's tokenization.

### Embedding Model
- **Model:** all-MiniLM-L6-v2 (sentence-transformers)
- **Dimension:** 384
- **Why:** Fast, lightweight, good quality for development. Can switch to all-mpnet-base-v2 (768-dim, more accurate) in Phase 4 if needed.
- **Tested:** Similar texts score ~0.58 cosine similarity; unrelated texts score ~0.00.

### Retrieval
- **Dense:** ChromaDB cosine similarity search on embeddings
- **BM25:** rank-bm25 keyword search (tokenized by whitespace + lowercased)
- **Hybrid merging:** Reciprocal Rank Fusion (RRF) with k=60. Each retriever returns 2*K candidates, then RRF combines ranks. This is preferred over score averaging because dense and BM25 scores are on different scales.
- **Default K:** 5 chunks returned per query

### Storage
- **ChromaDB** with persistent local storage at `./chroma_db`
- **BM25 index** rebuilt from ChromaDB on server startup (in-memory)

## Known Limitations
- Pages without extractable text (scanned images) are skipped — ColPali will handle these in Phase 3
- BM25 index is in-memory; rebuilt from ChromaDB on each restart
- No duplicate document detection — re-ingesting the same PDF creates duplicate chunks
- Token counts use cl100k_base encoding, which is close but not exactly Claude's tokenizer

## API Endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/health` | GET | Health check |
| `/api/ingest` | POST | Upload and process a PDF |
| `/api/retrieve` | POST | Query chunks (hybrid/dense/bm25) |
| `/api/documents` | GET | List ingested documents |
| `/api/clear` | DELETE | Clear all data (dev only) |
| `/api/debug` | GET | System info and stats |
