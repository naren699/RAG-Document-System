# FARE Document Q&A

FARE (Fast Augmented Retrieval Engine) is a RAG-based document question answering system. Upload PDF documents and ask natural language questions -- the system retrieves relevant passages using hybrid search, reranks them with a cross-encoder, and generates cited answers via an LLM.

Key features: hybrid retrieval (dense + BM25 with RRF fusion), cross-encoder reranking, heading-aware chunking, page classification (text vs visual), optional ColPali visual page embeddings, SSE streaming answers with inline citations, grounding score verification, conversation history, and thumbs up/down feedback. Supports Gemini, Claude, and OpenRouter as LLM backends.

## Team

- **NARENDHIRAN P**
- **LAKSHMIDHAR N**
- **DAKSHINA MOORTHY N D**

## Architecture

```
Ingestion:
  Upload PDF --> Classify Pages --> Extract Text --> Chunk (heading-aware, 300 tokens)
            --> Embed (all-MiniLM-L6-v2, 384-dim) --> ChromaDB (cosine)
            --> BM25 Index

Query:
  Query --> Embed --> Dense Search (ChromaDB) + BM25 Keyword Search
        --> RRF Merge --> Cross-Encoder Rerank (ms-marco-MiniLM-L-6-v2)
        --> Format Context --> LLM (streaming) --> Grounding Check --> SSE Response

Optional Visual Path (ColPali):
  Visual Pages --> Render as Image --> ColPali Embed (128-dim) --> Visual Collection
  Query --> ColPali Query Embed --> Visual Search --> Merge with Text Results
```

## Tech Stack

| Layer | Tool |
|---|---|
| Frontend | React 19 + Vite 8 + Tailwind CSS 4 |
| Backend | FastAPI + Uvicorn |
| Vector DB | ChromaDB (cosine metric) |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2, 384-dim) |
| Reranker | cross-encoder/ms-marco-MiniLM-L-6-v2 |
| Keyword Search | BM25 (rank-bm25) |
| Visual Pages | ColPali v1.2 (optional, GPU recommended) |
| LLM | Gemini / Claude / OpenRouter (configurable) |
| Tokenizer | tiktoken (cl100k_base) |

## Quick Start

Prerequisites: Python 3.12+, Node 18+

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate    # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # Edit with your API keys
uvicorn app:app --reload --host 0.0.0.0 --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 in your browser.

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `gemini` | LLM backend: `gemini`, `claude`, or `openrouter` |
| `GEMINI_API_KEY` | | Google Gemini API key |
| `GEMINI_MODEL` | `gemini-3.8-flash` | Gemini model ID |
| `ANTHROPIC_API_KEY` | | Anthropic API key (for Claude provider) |
| `CLAUDE_MODEL` | `claude-sonnet-4-20250514` | Claude model ID |
| `OPENROUTER_API_KEY` | | OpenRouter API key |
| `OPENROUTER_MODEL` | `google/gemini-3.8-flash` | OpenRouter model ID |
| `COLPALI_ENABLED` | `false` | Enable ColPali visual page embeddings (requires GPU) |
| `CHROMA_DB_PATH` | `./chroma_db` | ChromaDB persistent storage path |
| `SCORE_THRESHOLD` | `0.1` | Minimum reranker score to keep a chunk |

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/api/ingest` | Upload and process a PDF (multipart form) |
| GET | `/api/documents` | List all ingested documents |
| DELETE | `/api/documents/{doc_id}` | Delete a specific document |
| POST | `/api/documents/{doc_id}/rechunk` | Re-chunk a document with new settings |
| POST | `/api/query` | Query documents (non-streaming) |
| POST | `/api/query/stream` | Query documents (SSE streaming) |
| POST | `/api/feedback` | Submit thumbs up/down feedback |
| DELETE | `/api/clear` | Delete all documents and reset |
| GET | `/api/stats` | ChromaDB collection statistics |
| GET | `/api/debug` | Debug info (provider, model, config) |
| GET | `/api/eval/quick` | Run quick evaluation with built-in test cases |

## Running Tests

```bash
cd backend
python -m pytest tests/ -v
```

## Evaluation

```bash
cd backend

# Run all evaluation scripts
python -I eval_all.py

# Generate metrics dashboard
python -I eval_dashboard.py

# Evaluate page classifier accuracy
python -I eval_classifier.py

# Manual labeling of test results
python -I eval_manual_labels.py

# Visual retrieval evaluation (requires COLPALI_ENABLED=true)
python -I eval_visual.py
```

Results are written to `docs/`.

## Project Structure

```
backend/
  app.py                  # FastAPI application, all endpoints
  llm_provider.py         # LLM routing (Gemini/Claude/OpenRouter), streaming
  retriever.py            # Hybrid retrieval (dense + BM25 + RRF + rerank)
  reranker.py             # Cross-encoder reranking
  vector_store.py         # ChromaDB text + visual collections
  bm25_retriever.py       # BM25 keyword search
  embedder.py             # Sentence-transformer embeddings
  chunker.py              # Heading-aware token chunking
  pdf_extractor.py        # PDF text extraction via pdfplumber
  page_classifier.py      # Text vs visual page classification
  colpali_processor.py    # ColPali visual page embeddings
  grounding.py            # Answer grounding/faithfulness check
  eval_all.py             # Master evaluation runner
  eval_dashboard.py       # Metrics report generator
  eval_classifier.py      # Page classifier accuracy evaluation
  tests/                  # pytest test suite

frontend/
  src/
    App.jsx               # Main application component
    components/
      UploadSection.jsx   # PDF upload with drag-and-drop
      DocumentList.jsx    # Document management, re-chunking
      QuerySection.jsx    # Search input with elapsed timer
      ResultsSection.jsx  # Answer display, sources, score breakdown
      SettingsPanel.jsx   # Retrieval settings (K, method, threshold)
      ChunkModal.jsx      # Expanded chunk viewer
      HighlightedText.jsx # Query keyword highlighting

docs/
  test-queries.csv        # 50 test queries across categories
```

## License

Private -- academic project.
