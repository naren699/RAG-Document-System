# FARE Architecture

## Overview

FARE is a Retrieval-Augmented Generation (RAG) system. Instead of asking an LLM to answer from memory, we first find the relevant parts of a document and give them to the LLM as context.

## Pipeline

### 1. Document Ingestion (happens once per PDF)

```
PDF upload
    │
    ▼
Page Classification ──► Text-only page ──► Extract text (pdfplumber)
    │                                           │
    │                                           ▼
    │                                      Chunk text (tiktoken, ~500 tokens, 50 overlap)
    │                                           │
    │                                           ▼
    │                                      Generate embeddings (sentence-transformers)
    │                                           │
    │                                           ▼
    │                                      Store in ChromaDB
    │
    └──► Visual page (tables/charts/images) ──► ColPali (visual embedding)
                                                    │
                                                    ▼
                                               Store in ChromaDB
```

### 2. Query Processing (every question)

```
User question
    │
    ├──► Dense retrieval: embed question → find nearest chunks in ChromaDB
    │
    ├──► BM25 retrieval: keyword-match question against chunk text
    │
    └──► ColPali retrieval: match question against visual page embeddings
         │
         ▼
    Merge & rank results
         │
         ▼
    Send top-k chunks + question to Claude
         │
         ▼
    Claude generates answer (or says "I don't know")
         │
         ▼
    Return answer + source chunks to user
```

### 3. Evaluation

| Metric | What it measures | Target |
|---|---|---|
| Abstention Rate | Does the system say "I don't know" when the answer isn't in the document? | ≥ 90% |
| Hallucination Score | Is the answer supported by the retrieved chunks? | ≥ 85% |
| Context Efficiency | Were the retrieved chunks actually relevant, or wasted tokens? | Tracked |

## Key Decisions

### Chunking
- **Size:** ~500 tokens per chunk
- **Overlap:** 50 tokens between consecutive chunks
- **Tokenizer:** tiktoken (matches how Claude counts tokens)
- **Why overlap:** prevents losing information that spans a chunk boundary

### Embedding Model
- **Model:** all-MiniLM-L6-v2 (sentence-transformers)
- **Why:** lightweight, fast, good quality for semantic similarity
- **Dimension:** 384

### Hybrid Search
- **Dense (embeddings):** captures semantic meaning — "car" matches "vehicle"
- **BM25 (keywords):** captures exact matches — "Section 4.2" matches "Section 4.2"
- **Why both:** neither is perfect alone. Dense misses exact terms; BM25 misses synonyms.

### ColPali
- **What:** a vision-language model that reads a page as an image
- **Why:** text extractors destroy tables, charts, and figures. ColPali sees them visually.
- **When:** only for pages classified as having visual content

### LLM
- **Model:** Claude (Anthropic)
- **Prompt strategy:** "Answer using ONLY this context. If the answer isn't there, say you don't know."
- **Why Claude:** strong instruction following, good at abstaining

### Vector Database
- **ChromaDB** — local, embedded, no infrastructure needed
- **Why:** simple for a research project, no server to manage

## No LangChain

Every step is written in plain Python. This means:
- Full control over chunking, retrieval, and prompting
- Easy to run ablations (turn off one component, measure the difference)
- Every step is explainable in interviews and the research paper
