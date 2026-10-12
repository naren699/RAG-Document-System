# Error Handling

## API Error Responses

| Scenario | Endpoint | Status | Message |
|---|---|---|---|
| Empty query | `/api/query` | 400 | "Query cannot be empty" |
| Query too long (>500 chars) | `/api/query` | 400 | "Query too long (max 500 characters)" |
| No documents uploaded | `/api/query` | 400 | "No documents uploaded. Please ingest a PDF first." |
| Non-PDF file uploaded | `/api/ingest` | 400 | "Only PDF files are accepted" |
| File too large (>50MB) | `/api/ingest` | 400 | "File exceeds 50MB limit" |
| No extractable text | `/api/ingest` | 400 | "No content could be extracted from the PDF" |
| Invalid API key | `/api/query` | 500 | "Invalid Gemini API key. Check GEMINI_API_KEY in .env" |
| Rate limited | `/api/query` | 429 | "Gemini API rate limited. Try again later." |
| Unknown retrieval method | `/api/query` | 400 | "Unknown method: ..." |
| Unknown LLM provider | `/api/query` | 500 | "Unknown LLM provider: ..." |

## Debugging

- All errors are logged to `backend/fare.log`
- Use `/api/debug` to check system state
- Use `/api/documents` to verify documents are ingested
