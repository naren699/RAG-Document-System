import pdfplumber
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


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
    with pdfplumber.open(pdf_path) as pdf:
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

            pages.append({
                "page_num": i + 1,
                "text": text.strip(),
                "has_text": bool(text.strip()),
            })

    text_pages = sum(1 for p in pages if p["has_text"])
    logger.info(f"Extracted {text_pages}/{total} pages with text from {path.name}")
    return pages
