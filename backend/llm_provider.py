import logging
import os
import time

logger = logging.getLogger(__name__)

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")

_gemini_client = None
_claude_client = None

SYSTEM_PROMPT = """You are a document Q&A assistant for the FARE system.

Rules:
1. Answer using ONLY the provided context. Do not use your training knowledge.
2. If the answer is not in the context, respond exactly: "I don't have that information in the provided documents."
3. Be concise and factual. Cite the page number when possible (e.g., "According to page 3...").
4. If the context contains conflicting information, note both viewpoints.
5. Do not speculate or infer beyond what the context states.
6. If you can only partially answer the question, answer what you can and state what is missing."""


def format_context(chunks: list[dict]) -> str:
    """Format retrieved chunks into a readable context string."""
    parts = []
    for i, chunk in enumerate(chunks, 1):
        source = chunk.get("source", f"page {chunk.get('page_num', '?')}")
        score = chunk.get("score", 0)
        text = chunk.get("text", "")
        parts.append(
            f"[Source {i}: {source} | Relevance: {score:.2f}]\n{text}"
        )
    return "\n\n---\n\n".join(parts)


def format_user_message(context: str, query: str) -> str:
    """Format the user message with context and query."""
    return f"""Context:
{context}

Question: {query}

Answer:"""


def get_llm_provider() -> str:
    """Return the current LLM provider name."""
    return LLM_PROVIDER


def query_llm(context: str, query: str) -> dict:
    """Route to the appropriate LLM provider."""
    provider = get_llm_provider()

    if provider == "gemini":
        return query_with_gemini(context, query)
    elif provider == "claude":
        return query_with_claude(context, query)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}. Set LLM_PROVIDER to 'gemini' or 'claude'.")


def query_with_gemini(context: str, query: str) -> dict:
    """Call Gemini API and return answer with token counts."""
    global _gemini_client

    from google import genai

    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY not set in environment")

    if _gemini_client is None:
        _gemini_client = genai.Client(api_key=GEMINI_API_KEY)
        logger.info(f"Gemini client initialized: {GEMINI_MODEL}")

    user_message = format_user_message(context, query)

    start = time.time()
    try:
        response = _gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=user_message,
            config=genai.types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                max_output_tokens=1024,
            ),
        )
        elapsed_ms = int((time.time() - start) * 1000)

        answer = response.text

        input_tokens = 0
        output_tokens = 0
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            input_tokens = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
            output_tokens = getattr(response.usage_metadata, "candidates_token_count", 0) or 0

        logger.info(
            f"Gemini response: {input_tokens} in, {output_tokens} out, {elapsed_ms}ms"
        )

        return {
            "answer": answer,
            "provider": "gemini",
            "model": GEMINI_MODEL,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "generation_time_ms": elapsed_ms,
        }

    except Exception as e:
        elapsed_ms = int((time.time() - start) * 1000)
        logger.error(f"Gemini API error after {elapsed_ms}ms: {e}", exc_info=True)
        error_msg = str(e)
        if "API_KEY" in error_msg.upper() or "authentication" in error_msg.lower():
            raise ValueError("Invalid Gemini API key. Check GEMINI_API_KEY in .env")
        if "quota" in error_msg.lower() or "rate" in error_msg.lower():
            raise RuntimeError("Gemini API rate limited. Try again later.")
        raise


def query_with_claude(context: str, query: str) -> dict:
    """Call Claude API and return answer with token counts."""
    global _claude_client

    import anthropic

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set in environment")

    if _claude_client is None:
        _claude_client = anthropic.Anthropic(api_key=api_key)
        logger.info(f"Claude client initialized: {CLAUDE_MODEL}")

    user_message = format_user_message(context, query)

    start = time.time()
    try:
        response = _claude_client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        elapsed_ms = int((time.time() - start) * 1000)

        answer = response.content[0].text
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens

        logger.info(
            f"Claude response: {input_tokens} in, {output_tokens} out, {elapsed_ms}ms"
        )

        return {
            "answer": answer,
            "provider": "claude",
            "model": CLAUDE_MODEL,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "generation_time_ms": elapsed_ms,
        }

    except Exception as e:
        elapsed_ms = int((time.time() - start) * 1000)
        logger.error(f"Claude API error after {elapsed_ms}ms: {e}", exc_info=True)
        raise


def generate_answer(query: str, chunks: list[dict]) -> dict:
    """High-level function: format context from chunks, call LLM, return result."""
    if not chunks:
        return {
            "answer": "I don't have that information in the provided documents.",
            "provider": get_llm_provider(),
            "model": GEMINI_MODEL if get_llm_provider() == "gemini" else CLAUDE_MODEL,
            "input_tokens": 0,
            "output_tokens": 0,
            "generation_time_ms": 0,
        }

    context = format_context(chunks)
    return query_llm(context, query)
