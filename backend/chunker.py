import tiktoken
import logging
import os

logger = logging.getLogger(__name__)

CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "500"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "50"))

_encoder = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    return len(_encoder.encode(text))


def chunk_text(
    text: str,
    chunk_size: int = None,
    chunk_overlap: int = None,
) -> list[str]:
    """Split text into token-aware chunks, preferring paragraph boundaries."""
    if chunk_size is None:
        chunk_size = CHUNK_SIZE
    if chunk_overlap is None:
        chunk_overlap = CHUNK_OVERLAP

    if not text.strip():
        return []

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]

    chunks = []
    current_chunk = ""
    current_tokens = 0

    for para in paragraphs:
        para_tokens = count_tokens(para)

        if para_tokens > chunk_size:
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = ""
                current_tokens = 0
            chunks.extend(_split_long_paragraph(para, chunk_size, chunk_overlap))
            continue

        if current_tokens + para_tokens > chunk_size and current_chunk:
            chunks.append(current_chunk)
            overlap_text = _get_overlap(current_chunk, chunk_overlap)
            current_chunk = overlap_text + "\n\n" + para if overlap_text else para
            current_tokens = count_tokens(current_chunk)
        else:
            current_chunk = current_chunk + "\n\n" + para if current_chunk else para
            current_tokens = count_tokens(current_chunk)

    if current_chunk.strip():
        chunks.append(current_chunk)

    return chunks


def _split_long_paragraph(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    """Split a single paragraph that exceeds chunk_size by sentence boundaries."""
    sentences = []
    for part in text.replace(". ", ".\n").split("\n"):
        part = part.strip()
        if part:
            sentences.append(part)

    chunks = []
    current = ""
    current_tokens = 0

    for sent in sentences:
        sent_tokens = count_tokens(sent)
        if current_tokens + sent_tokens > chunk_size and current:
            chunks.append(current)
            overlap_text = _get_overlap(current, chunk_overlap)
            current = overlap_text + " " + sent if overlap_text else sent
            current_tokens = count_tokens(current)
        else:
            current = current + " " + sent if current else sent
            current_tokens = count_tokens(current)

    if current.strip():
        chunks.append(current)

    return chunks


def _get_overlap(text: str, overlap_tokens: int) -> str:
    """Return the last `overlap_tokens` tokens of text as a string."""
    if overlap_tokens <= 0:
        return ""
    tokens = _encoder.encode(text)
    if len(tokens) <= overlap_tokens:
        return text
    return _encoder.decode(tokens[-overlap_tokens:])


def chunk_document(pages: list[dict], doc_id: str, chunk_size: int = None, chunk_overlap: int = None) -> list[dict]:
    """Chunk all pages of a document, preserving page metadata."""
    all_chunks = []
    chunk_index = 0

    for page in pages:
        if not page["has_text"]:
            continue

        page_chunks = chunk_text(page["text"], chunk_size, chunk_overlap)

        for text in page_chunks:
            all_chunks.append({
                "chunk_id": f"{doc_id}_chunk_{chunk_index}",
                "doc_id": doc_id,
                "page_num": page["page_num"],
                "text": text,
                "token_count": count_tokens(text),
                "source": f"{doc_id}, page {page['page_num']}",
            })
            chunk_index += 1

    logger.info(f"Created {len(all_chunks)} chunks from {doc_id}")
    return all_chunks
