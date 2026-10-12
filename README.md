# FARE — Faithful Abstaining RAG Evaluator

A Retrieval-Augmented Generation (RAG) system for document Q&A, built from scratch in plain Python.

## What it does

Upload a PDF, ask a question, get an answer grounded in the document — or an honest "I don't know" when the answer isn't there.

## Team

- **Lakshmidhar** 
- **Dakshina Moorthy**

## Tech Stack

| Layer | Tool |
|---|---|
| Frontend | React + Vite + Tailwind CSS |
| Backend | FastAPI + Uvicorn |
| Vector DB | ChromaDB |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) |
| Keyword Search | BM25 (rank-bm25) |
| Visual Pages | ColPali |
| LLM | Claude API (Anthropic) |
| Tokenizer | tiktoken |

## Architecture

```
PDF → page classifier → text path (chunk → embed → BM25 + dense search)
                       → visual path (ColPali)
                       → merge results → Claude generates answer → evaluate
```

## Quick Start

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env       # Fill in your API keys
python app.py
```

Server runs at http://localhost:8000

### Frontend

```bash
cd frontend
npm install
npm run dev
```

App runs at http://localhost:5173

## Project Structure

```
fare-rag/
├── backend/          # FastAPI server, RAG pipeline
│   ├── app.py        # Entry point
│   ├── requirements.txt
│   └── .env.example
├── frontend/         # React UI
├── data/             # Sample PDFs (not committed)
├── docs/             # Architecture docs, diagrams
└── README.md
```

## License

Private — academic project.
