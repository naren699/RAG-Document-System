import re
import tiktoken
import logging
import os

logger = logging.getLogger(__name__)

CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "300"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "50"))
MIN_CHUNK_TOKENS = 10

_encoder = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    return len(_encoder.encode(text))


_HEADING_PATTERNS = [
    re.compile(r'^#{1,3}\s+.+'),
    re.compile(r'^[A-Z][A-Z\s&/,.\-]{2,}$'),
    re.compile(r'^(?:PROFESSIONAL\s+SUMMARY|SUMMARY|OBJECTIVE|EXPERIENCE|WORK\s+EXPERIENCE|EDUCATION|SKILLS|TECHNICAL\s+SKILLS|PROJECTS|CERTIFICATIONS?|AWARDS?|ACHIEVEMENTS?|PUBLICATIONS?|INTERESTS?|LANGUAGES?|REFERENCES?|CONTACT|PROFILE|ABOUT\s+ME)[\s:]*$', re.IGNORECASE),
    re.compile(r'^\d+[.)]\s+[A-Z]'),
    re.compile(r'^[A-Z][a-zA-Z\s]{2,50}:$'),
    re.compile(r'^[A-Z][A-Z\s&/,.\-]{2,}:'),
]


def _is_heading(line: str) -> bool:
    stripped = line.strip()
    if not stripped or len(stripped) < 3 or len(stripped) > 100:
        return False
    for pat in _HEADING_PATTERNS:
        if pat.match(stripped):
            return True
    return False


def _extract_heading_title(line: str) -> str:
    stripped = line.strip().rstrip(':').strip()
    stripped = re.sub(r'^#{1,3}\s+', '', stripped)
    stripped = re.sub(r'^\d+[.)]\s+', '', stripped)
    return stripped


def _split_into_sections(text: str) -> list[dict]:
    """Split text into sections based on heading detection.

    Returns list of {"title": str|None, "text": str}.
    """
    lines = text.split('\n')
    sections = []
    current_title = None
    current_lines = []

    for line in lines:
        stripped = line.strip()
        if _is_heading(stripped) and len(stripped) < 80:
            if current_lines:
                body = '\n'.join(current_lines).strip()
                if body:
                    sections.append({"title": current_title, "text": body})
            current_title = _extract_heading_title(stripped)
            current_lines = []
        else:
            current_lines.append(line)

    if current_lines:
        body = '\n'.join(current_lines).strip()
        if body:
            sections.append({"title": current_title, "text": body})

    if not sections and text.strip():
        sections = [{"title": None, "text": text.strip()}]

    return sections


def chunk_text(
    text: str,
    chunk_size: int = None,
    chunk_overlap: int = None,
) -> list[str]:
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
    sentences = re.split(r'(?<=[.!?])\s+', text)
    sentences = [s.strip() for s in sentences if s.strip()]

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
    if overlap_tokens <= 0:
        return ""
    tokens = _encoder.encode(text)
    if len(tokens) <= overlap_tokens:
        return text
    return _encoder.decode(tokens[-overlap_tokens:])


def chunk_document(pages: list[dict], doc_id: str, chunk_size: int = None, chunk_overlap: int = None) -> list[dict]:
    """Chunk pages using section-aware splitting: detect headings first, then token-split within sections."""
    if chunk_size is None:
        chunk_size = CHUNK_SIZE
    if chunk_overlap is None:
        chunk_overlap = CHUNK_OVERLAP

    full_text = ""
    page_breaks = []
    for page in pages:
        if not page["has_text"]:
            continue
        start = len(full_text)
        if full_text:
            full_text += "\n\n"
            start = len(full_text)
        full_text += page["text"]
        page_breaks.append({"page_num": page["page_num"], "start": start, "end": len(full_text)})

    if not full_text.strip():
        return []

    def _find_page(char_pos: int) -> int:
        for pb in page_breaks:
            if pb["start"] <= char_pos < pb["end"]:
                return pb["page_num"]
        return page_breaks[-1]["page_num"] if page_breaks else 1

    sections = _split_into_sections(full_text)

    all_chunks = []
    chunk_index = 0

    for section in sections:
        section_text = section["text"]
        section_title = section["title"]
        section_tokens = count_tokens(section_text)

        if section_tokens <= chunk_size:
            text_pieces = [section_text]
        else:
            text_pieces = chunk_text(section_text, chunk_size, chunk_overlap)

        section_start = full_text.find(section_text)
        for text in text_pieces:
            piece_start = full_text.find(text[:50], max(0, section_start - 10)) if len(text) >= 50 else section_start
            if piece_start < 0:
                piece_start = section_start
            page_num = _find_page(piece_start)

            source_parts = [doc_id, f"page {page_num}"]
            if section_title:
                source_parts.append(section_title)

            all_chunks.append({
                "chunk_id": f"{doc_id}_chunk_{chunk_index}",
                "doc_id": doc_id,
                "page_num": page_num,
                "section_title": section_title,
                "text": text,
                "token_count": count_tokens(text),
                "source": ", ".join(source_parts),
            })
            chunk_index += 1

    logger.info(f"Created {len(all_chunks)} chunks from {doc_id} ({len(sections)} sections detected)")
    return all_chunks
