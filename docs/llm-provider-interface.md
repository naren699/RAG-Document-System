# LLM Provider Interface

FARE supports multiple LLM providers through an abstraction layer in `backend/llm_provider.py`.

## Switching Providers

Change one line in `backend/.env`:

```
LLM_PROVIDER=gemini    # Use Google Gemini
LLM_PROVIDER=claude    # Use Anthropic Claude
```

## Current Providers

### Gemini (default)
- Model: `gemini-2.0-flash`
- Requires: `GEMINI_API_KEY` in `.env`
- Get key: https://aistudio.google.com/app/apikeys

### Claude
- Model: `claude-sonnet-4-20250514`
- Requires: `ANTHROPIC_API_KEY` in `.env`
- Get key: https://console.anthropic.com/

## Interface

Every provider function has the same signature:

```python
def query_with_<provider>(context: str, query: str) -> dict:
    """
    Input:
        context: formatted text from retrieved chunks
        query: the user's question

    Output:
        {
            "answer": str,         # the generated answer
            "provider": str,       # "gemini" or "claude"
            "model": str,          # model name
            "input_tokens": int,   # tokens in (context + query)
            "output_tokens": int,  # tokens out (answer)
            "generation_time_ms": int,  # API call time
        }
    """
```

## Adding a New Provider

1. Add a `query_with_<name>()` function in `llm_provider.py`
2. Add the provider to the `query_llm()` routing function
3. Add the API key to `.env.example`
4. No changes needed to `app.py` or the frontend
