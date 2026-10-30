# FARE Document Q&A - Demo Script

## Prerequisites

- Backend running: `cd backend && uvicorn app:app --reload`
- Frontend running: `cd frontend && npm run dev`
- Open browser at http://localhost:5173

## Demo Flow (2-3 minutes)

### 1. Upload a Document

- Drag and drop `data/test_sample.pdf` into the upload zone
- Note the privacy warning about external AI provider
- After upload: see "Uploaded! X chunks created from Y pages"
- Show the document in the document list

### 2. Ask a Factual Question

- Type: "What is machine learning?"
- Watch the elapsed timer while searching
- Point out:
  - Streaming answer with citation chips [1], [2]
  - Answer status badge (Grounded / Partially grounded)
  - Source cards with relevance scores and score breakdown (Dense, BM25, RRF, Rerank)
  - Grounding percentage in timing details
  - Context efficiency line (tokens, chunks, cited count)
  - Retrieved vs kept count

### 3. Follow-up Question

- Type: "How does it relate to deep learning?"
- Show that conversation history provides context
- Previous Q&A appears in conversation history section

### 4. Out-of-Scope Question

- Type: "What is the recipe for chocolate cake?"
- Show the blue "Not found in documents" response
- System correctly abstains from answering

### 5. Explore Source Details

- Click on a source card to open the chunk modal
- Show "Show more" / "Show less" on long chunks
- Toggle uncited sources with "Show X more retrieved sources"

### 6. Settings and Re-chunking

- Open Settings panel
- Change Top K from 5 to 3
- Show the Re-chunk button on the document list
- Adjust chunk size, re-chunk, verify chunk count changes

### 7. Export

- Click JSON or TXT buttons to download the answer
- Show the downloaded file

### 8. Thumbs Up/Down Feedback

- Click thumbs up on a good answer
- Feedback is logged to feedback.jsonl

## Key Features to Highlight

- Hybrid retrieval (Dense + BM25 + RRF + Cross-encoder reranking)
- Real-time SSE streaming with timing breakdowns
- Grounding score validates answer faithfulness
- Citation-based answers with clickable source references
- Heading-aware chunking for better text segmentation
- Privacy notice for external AI provider usage
- Conversation history for follow-up questions
