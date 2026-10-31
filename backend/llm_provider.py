import logging
import os
import re
import time

logger = logging.getLogger(__name__)

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemini-3.8-flash")

_gemini_client = None
_claude_client = None
_openrouter_client = None

SYSTEM_PROMPT = """You are a document Q&A assistant.

Rules:
1. Answer using ONLY the provided context. Never use training knowledge.
2. If the answer is NOT in the context, respond ONLY with: "I couldn't find this in the uploaded documents."
   Do not add any other text, do not guess, and do not use training knowledge.
3. Cite sources inline as [1], [2], etc. Only cite sources that directly support each statement.
4. Answer directly — start with the information itself.
   FORBIDDEN phrases: "Based on the provided context", "According to the documents",
   "Based on the information", "The context shows", "From the provided", "Looking at the context".
   Just state the facts naturally.
5. Be concise and factual.
6. If the context contains conflicting information, note both viewpoints with their citations.
7. Do not speculate or infer beyond what the context states.
8. If you can only partially answer, answer what you can with citations and note what is missing."""

COST_PER_1M_TOKENS = {
    "gemini-3.8-flash": {"input": 0.10, "output": 0.40},
    "gemini-2.5-flash-preview": {"input": 0.15, "output": 0.60},
    "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
    "google/gemini-3.8-flash": {"input": 0.10, "output": 0.40},
    "google/gemini-2.5-flash-preview": {"input": 0.15, "output": 0.60},
}

_tokenizer = None


def _get_tokenizer():
    global _tokenizer
    if _tokenizer is None:
        import tiktoken
        _tokenizer = tiktoken.get_encoding("cl100k_base")
    return _tokenizer


def _estimate_input_tokens(system_prompt: str, user_message: str) -> int:
    """Estimate input tokens using tiktoken when API doesn't return usage."""
    enc = _get_tokenizer()
    return len(enc.encode(system_prompt)) + len(enc.encode(user_message)) + 10


def _estimate_output_tokens(text: str) -> int:
    """Estimate output tokens using tiktoken."""
    enc = _get_tokenizer()
    return len(enc.encode(text))


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float | None:
    pricing = COST_PER_1M_TOKENS.get(model)
    if not pricing:
        return None
    cost = (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000
    return round(cost, 6)


_EMAIL_RE = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')
_PHONE_RE = re.compile(r'(?:\+?\d{1,3}[\s\-]?)?\(?\d{2,4}\)?[\s\-]?\d{3,5}[\s\-]?\d{3,5}')


def mask_pii(text: str) -> str:
    """Replace emails and phone numbers with placeholders."""
    text = _EMAIL_RE.sub('[EMAIL]', text)
    text = _PHONE_RE.sub('[PHONE]', text)
    return text


def format_context(chunks: list[dict], mask: bool = False) -> str:
    """Format retrieved chunks into a numbered context string for citation."""
    parts = []
    for i, chunk in enumerate(chunks, 1):
        source = chunk.get("source", f"page {chunk.get('page_num', '?')}")
        text = chunk.get("text", "")
        if mask:
            text = mask_pii(text)
        parts.append(f"[{i}] (Source: {source})\n{text}")
    return "\n\n---\n\n".join(parts)


def format_user_message(context: str, query: str, history: list[dict] | None = None) -> str:
    """Format the user message with optional conversation history, context, and query."""
    parts = []
    if history:
        recent = history[-6:]
        parts.append("Previous conversation:")
        for msg in recent:
            role = msg.get("role", "user").capitalize()
            parts.append(f"{role}: {msg.get('content', '')}")
        parts.append("")
    parts.append(f"Context:\n{context}")
    parts.append(f"\nQuestion: {query}")
    parts.append("\nAnswer:")
    return "\n".join(parts)


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
    elif provider == "openrouter":
        return query_with_openrouter(context, query)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}. Set LLM_PROVIDER to 'gemini', 'claude', or 'openrouter'.")


def query_with_gemini(context: str, query: str) -> dict:
    """Call Gemini API and return answer with token counts."""
    global _gemini_client

    from google import genai

    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY not set in environment")

    if _gemini_client is None:
        _gemini_client = genai.Client(
            api_key=GEMINI_API_KEY,
            http_options={"timeout": 30_000},
        )
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
        if elapsed_ms > 10_000:
            logger.warning(f"SLOW API CALL: {elapsed_ms}ms for {GEMINI_MODEL}")

        return {
            "answer": answer,
            "provider": "gemini",
            "model": GEMINI_MODEL,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "generation_time_ms": elapsed_ms,
            "estimated_cost_usd": _estimate_cost(GEMINI_MODEL, input_tokens, output_tokens),
        }

    except Exception as e:
        elapsed_ms = int((time.time() - start) * 1000)
        logger.error(f"Gemini API error after {elapsed_ms}ms: {e}", exc_info=True)
        error_msg = str(e)
        if "API_KEY" in error_msg.upper() or "authentication" in error_msg.lower():
            raise ValueError("Invalid Gemini API key. Check GEMINI_API_KEY in .env")
        if any(kw in error_msg.lower() for kw in ("quota", "rate", "unavailable", "high demand", "deadline", "503", "504", "429")):
            raise RuntimeError("Gemini API rate limited or unavailable. Try again later.")
        if "closed" in error_msg.lower():
            raise RuntimeError("Gemini API connection error. Please retry.")
        raise


def query_with_claude(context: str, query: str) -> dict:
    """Call Claude API and return answer with token counts."""
    global _claude_client

    import anthropic

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set in environment")

    if _claude_client is None:
        _claude_client = anthropic.Anthropic(api_key=api_key, timeout=30.0)
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
        if elapsed_ms > 10_000:
            logger.warning(f"SLOW API CALL: {elapsed_ms}ms for {CLAUDE_MODEL}")

        return {
            "answer": answer,
            "provider": "claude",
            "model": CLAUDE_MODEL,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "generation_time_ms": elapsed_ms,
            "estimated_cost_usd": _estimate_cost(CLAUDE_MODEL, input_tokens, output_tokens),
        }

    except Exception as e:
        elapsed_ms = int((time.time() - start) * 1000)
        logger.error(f"Claude API error after {elapsed_ms}ms: {e}", exc_info=True)
        raise


def query_with_openrouter(context: str, query: str) -> dict:
    """Call OpenRouter API (OpenAI-compatible) and return answer with token counts."""
    global _openrouter_client

    from openai import OpenAI

    if not OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY not set in environment")

    if _openrouter_client is None:
        _openrouter_client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_API_KEY,
        )
        logger.info(f"OpenRouter client initialized: {OPENROUTER_MODEL}")

    user_message = format_user_message(context, query)

    start = time.time()
    try:
        response = _openrouter_client.chat.completions.create(
            model=OPENROUTER_MODEL,
            max_tokens=1024,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
        )
        elapsed_ms = int((time.time() - start) * 1000)

        answer = response.choices[0].message.content
        input_tokens = getattr(response.usage, "prompt_tokens", 0) or 0
        output_tokens = getattr(response.usage, "completion_tokens", 0) or 0

        logger.info(
            f"OpenRouter response: {input_tokens} in, {output_tokens} out, {elapsed_ms}ms"
        )

        return {
            "answer": answer,
            "provider": "openrouter",
            "model": OPENROUTER_MODEL,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "generation_time_ms": elapsed_ms,
            "estimated_cost_usd": _estimate_cost(OPENROUTER_MODEL, input_tokens, output_tokens),
        }

    except Exception as e:
        elapsed_ms = int((time.time() - start) * 1000)
        logger.error(f"OpenRouter API error after {elapsed_ms}ms: {e}", exc_info=True)
        raise


def generate_answer(query: str, chunks: list[dict]) -> dict:
    """High-level function: format context from chunks, call LLM, return result."""
    if not chunks:
        return {
            "answer": "I couldn't find this in the uploaded documents.",
            "provider": get_llm_provider(),
            "model": GEMINI_MODEL if get_llm_provider() == "gemini" else CLAUDE_MODEL,
            "input_tokens": 0,
            "output_tokens": 0,
            "generation_time_ms": 0,
        }

    context = format_context(chunks)
    return query_llm(context, query)


# ---------------------------------------------------------------------------
# Streaming generators
# ---------------------------------------------------------------------------

def _ensure_gemini_client():
    global _gemini_client
    from google import genai
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY not set in environment")
    if _gemini_client is None:
        _gemini_client = genai.Client(api_key=GEMINI_API_KEY, http_options={"timeout": 30_000})
        logger.info(f"Gemini client initialized: {GEMINI_MODEL}")
    return _gemini_client


def _ensure_claude_client():
    global _claude_client
    import anthropic
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set in environment")
    if _claude_client is None:
        _claude_client = anthropic.Anthropic(api_key=api_key, timeout=30.0)
        logger.info(f"Claude client initialized: {CLAUDE_MODEL}")
    return _claude_client


def _ensure_openrouter_client():
    global _openrouter_client
    from openai import OpenAI
    if not OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY not set in environment")
    if _openrouter_client is None:
        _openrouter_client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_API_KEY)
        logger.info(f"OpenRouter client initialized: {OPENROUTER_MODEL}")
    return _openrouter_client


VISION_TRANSCRIBE_PROMPT = """You are a document OCR assistant. Extract ALL text content from this page image.

Rules:
1. Preserve the original structure: headings, paragraphs, lists, table rows.
2. Use one blank line between sections. Use "# " prefix for section headings.
3. For tables, output as: "| col1 | col2 | col3 |" format.
4. For diagrams or charts, describe the data briefly: axes, labels, values, trends.
5. For infographics, transcribe ALL visible text and describe icons or visual elements in [brackets].
6. Output ONLY the extracted content. No commentary, preamble, or "Here is the text:".
7. If text is partially unreadable, write "[unreadable]" for that portion.
8. If the page is blank, output only: "[Blank page]"
9. Maintain reading order: left-to-right, top-to-bottom."""


def transcribe_page_with_vision(img: "Image.Image", page_num: int) -> dict:
    """Send a page image to the vision LLM for text transcription.

    Returns {text, input_tokens, output_tokens, generation_time_ms, estimated_cost_usd}.
    """
    import base64
    from io import BytesIO

    provider = get_llm_provider()
    if provider == "openrouter":
        client = _ensure_openrouter_client()
        model = OPENROUTER_MODEL
    elif provider == "gemini":
        from google import genai
        client = _ensure_gemini_client()
        model = GEMINI_MODEL
    else:
        raise ValueError(f"Vision transcription not supported for provider: {provider}")

    buf = BytesIO()
    img.save(buf, format="PNG")
    b64_image = base64.b64encode(buf.getvalue()).decode("utf-8")

    logger.info(f"Vision transcription page {page_num}: sending to {provider}/{model}")
    start = time.time()

    if provider == "openrouter":
        response = client.chat.completions.create(
            model=model,
            max_tokens=2048,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": VISION_TRANSCRIBE_PROMPT},
                    {"type": "image_url", "image_url": {
                        "url": f"data:image/png;base64,{b64_image}",
                    }},
                ],
            }],
        )
        elapsed_ms = int((time.time() - start) * 1000)
        text = response.choices[0].message.content
        input_tokens = getattr(response.usage, "prompt_tokens", 0) or 0
        output_tokens = getattr(response.usage, "completion_tokens", 0) or 0
    elif provider == "gemini":
        from google import genai
        import PIL.Image
        response = client.models.generate_content(
            model=model,
            contents=[VISION_TRANSCRIBE_PROMPT, img],
            config=genai.types.GenerateContentConfig(max_output_tokens=2048),
        )
        elapsed_ms = int((time.time() - start) * 1000)
        text = response.text
        input_tokens = 0
        output_tokens = 0
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            input_tokens = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
            output_tokens = getattr(response.usage_metadata, "candidates_token_count", 0) or 0

    logger.info(f"Vision transcription page {page_num}: {len(text)} chars, "
                f"{input_tokens} in / {output_tokens} out, {elapsed_ms}ms")

    return {
        "text": text,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "generation_time_ms": elapsed_ms,
        "estimated_cost_usd": _estimate_cost(model, input_tokens, output_tokens),
    }


def stream_with_gemini(context: str, query: str, history: list[dict] | None = None):
    """Yield text chunks from Gemini streaming API, then a usage sentinel dict."""
    from google import genai
    client = _ensure_gemini_client()
    user_message = format_user_message(context, query, history)

    response = client.models.generate_content_stream(
        model=GEMINI_MODEL,
        contents=user_message,
        config=genai.types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            max_output_tokens=1024,
        ),
    )
    last_chunk = None
    full_content = []
    for chunk in response:
        last_chunk = chunk
        if chunk.text:
            full_content.append(chunk.text)
            yield chunk.text

    input_tokens = 0
    output_tokens = 0
    estimated = False
    if last_chunk and hasattr(last_chunk, "usage_metadata") and last_chunk.usage_metadata:
        input_tokens = getattr(last_chunk.usage_metadata, "prompt_token_count", 0) or 0
        output_tokens = getattr(last_chunk.usage_metadata, "candidates_token_count", 0) or 0

    if input_tokens == 0:
        input_tokens = _estimate_input_tokens(SYSTEM_PROMPT, user_message)
        estimated = True
    if output_tokens == 0 and full_content:
        output_tokens = _estimate_output_tokens("".join(full_content))
        estimated = True

    yield {"__usage__": True, "input_tokens": input_tokens, "output_tokens": output_tokens, "estimated": estimated}


def stream_with_claude(context: str, query: str, history: list[dict] | None = None):
    """Yield text chunks from Claude streaming API, then a usage sentinel dict."""
    client = _ensure_claude_client()
    user_message = format_user_message(context, query, history)

    input_tokens = 0
    output_tokens = 0
    with client.messages.stream(
        model=CLAUDE_MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    ) as stream:
        for text in stream.text_stream:
            yield text
        final = stream.get_final_message()
        if final and final.usage:
            input_tokens = final.usage.input_tokens or 0
            output_tokens = final.usage.output_tokens or 0
    yield {"__usage__": True, "input_tokens": input_tokens, "output_tokens": output_tokens}


def stream_with_openrouter(context: str, query: str, history: list[dict] | None = None):
    """Yield text chunks from OpenRouter streaming API, then a usage sentinel dict."""
    client = _ensure_openrouter_client()
    user_message = format_user_message(context, query, history)

    response = client.chat.completions.create(
        model=OPENROUTER_MODEL,
        max_tokens=1024,
        stream=True,
        stream_options={"include_usage": True},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
    )
    input_tokens = 0
    output_tokens = 0
    full_content = []
    for chunk in response:
        if chunk.usage:
            input_tokens = getattr(chunk.usage, "prompt_tokens", 0) or 0
            output_tokens = getattr(chunk.usage, "completion_tokens", 0) or 0
        if chunk.choices:
            delta = chunk.choices[0].delta
            if delta and delta.content:
                full_content.append(delta.content)
                yield delta.content

    if input_tokens == 0:
        input_tokens = _estimate_input_tokens(SYSTEM_PROMPT, user_message)
    if output_tokens == 0 and full_content:
        output_tokens = _estimate_output_tokens("".join(full_content))

    yield {"__usage__": True, "input_tokens": input_tokens, "output_tokens": output_tokens, "estimated": input_tokens == _estimate_input_tokens(SYSTEM_PROMPT, user_message)}


def stream_llm(context: str, query: str, history: list[dict] | None = None):
    """Route to the appropriate streaming LLM provider. Yields text chunks."""
    provider = get_llm_provider()
    if provider == "gemini":
        yield from stream_with_gemini(context, query, history)
    elif provider == "claude":
        yield from stream_with_claude(context, query, history)
    elif provider == "openrouter":
        yield from stream_with_openrouter(context, query, history)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")


def get_model_name() -> str:
    """Return the current model name based on the provider."""
    provider = get_llm_provider()
    if provider == "gemini":
        return GEMINI_MODEL
    elif provider == "claude":
        return CLAUDE_MODEL
    elif provider == "openrouter":
        return OPENROUTER_MODEL
    return "unknown"


REWRITE_PROMPT = """Rewrite the follow-up question into a standalone question using the conversation history.
Only output the rewritten question, nothing else. If it's already standalone, return it unchanged.

Conversation:
{history}

Follow-up: {query}

Standalone question:"""


def rewrite_follow_up(query: str, history: list[dict]) -> str:
    """Rewrite a follow-up query into a standalone query using conversation history."""
    if not history or len(history) < 2:
        return query

    history_text = "\n".join(
        f"{'User' if m.get('role') == 'user' else 'Assistant'}: {m.get('content', '')[:200]}"
        for m in history[-6:]
    )
    prompt = REWRITE_PROMPT.format(history=history_text, query=query)

    provider = get_llm_provider()
    try:
        if provider == "gemini":
            client = _ensure_gemini_client()
            from google import genai
            resp = client.models.generate_content(
                model=GEMINI_MODEL, contents=prompt,
                config=genai.types.GenerateContentConfig(max_output_tokens=100),
            )
            return resp.text.strip() or query
        elif provider == "claude":
            client = _ensure_claude_client()
            resp = client.messages.create(
                model=CLAUDE_MODEL, max_tokens=100,
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.content[0].text.strip() or query
        elif provider == "openrouter":
            client = _ensure_openrouter_client()
            resp = client.chat.completions.create(
                model=OPENROUTER_MODEL, max_tokens=100,
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.choices[0].message.content.strip() or query
    except Exception as e:
        logger.warning(f"Query rewrite failed, using original: {e}")
    return query
