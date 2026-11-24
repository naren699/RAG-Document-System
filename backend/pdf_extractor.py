import pdfplumber
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)


def clean_extracted_text(text: str) -> str:
    """Clean common PDF extraction artifacts without changing content."""
    # Rejoin hyphenated line breaks: "Develop-\nment" → "Development"
    text = re.sub(r'(\w)-\s*\n\s*(\w)', r'\1\2', text)
    # Fix word broken at line boundary with no hyphen: "Developmen\nt" → "Development"
    text = re.sub(r'(\w{3,})\n([a-z]{1,3}\b)', r'\1\2', text)
    # Remove stray commas: ", ," or ",," or ", , ,"
    text = re.sub(r'(?:,\s*){2,}', ', ', text)
    # Remove leading/trailing commas on lines
    text = re.sub(r'^\s*,\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'\s*,\s*$', '', text, flags=re.MULTILINE)
    # Collapse multiple spaces to one
    text = re.sub(r'[ \t]{2,}', ' ', text)
    # Remove spaces before commas
    text = re.sub(r'\s+,', ',', text)
    # Ensure space after comma if missing (but not in numbers like 1,000)
    text = re.sub(r',([A-Za-z])', r', \1', text)
    # Collapse multiple blank lines to one
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def extract_text_from_pdf(pdf_path: str) -> list[dict]:
    """Extract text from each page of a PDF.

    Returns a list of dicts: [{"page_num": 1, "text": "..."}, ...]
    """
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    if path.suffix.lower() != ".pdf":
        raise ValueError(f"Not a PDF file: {pdf_path}")

    pages = []
    try:
        pdf_file = pdfplumber.open(pdf_path)
    except Exception as e:
        msg = str(e).lower()
        if "password" in msg or "encrypted" in msg:
            raise ValueError("This PDF is password-protected. Please remove the password and try again.")
        raise ValueError(f"Could not read PDF: {e}")

    with pdf_file as pdf:
        total = len(pdf.pages)
        logger.info(f"Extracting text from {path.name} ({total} pages)")

        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""

            if not text.strip():
                tables = page.extract_tables()
                if tables:
                    table_lines = []
                    for table in tables:
                        for row in table:
                            cleaned = [cell if cell else "" for cell in row]
                            table_lines.append(" | ".join(cleaned))
                    text = "\n".join(table_lines)

            cleaned = clean_extracted_text(text)
            pages.append({
                "page_num": i + 1,
                "text": cleaned,
                "has_text": bool(cleaned),
            })

    text_pages = sum(1 for p in pages if p["has_text"])
    logger.info(f"Extracted {text_pages}/{total} pages with text from {path.name}")
    return pages
