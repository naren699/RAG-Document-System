import pdfplumber
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

VISUAL_THRESHOLD = 0.15


def classify_pages(pdf_path: str) -> list[dict]:
    """Classify each page as 'text' or 'visual' based on non-text content.

    Uses a heuristic: if images/tables cover more than 15% of the page area,
    or if the page has very little extractable text relative to its visual
    content, it's classified as 'visual'.
    """
    path = Path(pdf_path)
    results = []

    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            page_num = i + 1
            page_area = page.width * page.height

            text = page.extract_text() or ""
            text_len = len(text.strip())

            image_area = 0
            for img in (page.images or []):
                w = abs(img.get("x1", 0) - img.get("x0", 0))
                h = abs(img.get("bottom", 0) - img.get("top", 0))
                image_area += w * h

            tables = page.extract_tables() or []
            table_area = 0
            for table_obj in (page.find_tables() or []):
                bbox = table_obj.bbox
                w = abs(bbox[2] - bbox[0])
                h = abs(bbox[3] - bbox[1])
                table_area += w * h

            visual_area = image_area + table_area
            visual_ratio = visual_area / page_area if page_area > 0 else 0

            has_tables = len(tables) > 0
            has_images = len(page.images or []) > 0
            text_sparse = text_len < 100 and (has_images or has_tables)

            is_visual = (
                visual_ratio > VISUAL_THRESHOLD
                or text_sparse
                or (has_tables and visual_ratio > 0.08)
            )

            page_type = "visual" if is_visual else "text"

            results.append({
                "page_num": page_num,
                "page_type": page_type,
                "text_length": text_len,
                "visual_ratio": round(visual_ratio, 3),
                "has_tables": has_tables,
                "has_images": has_images,
                "table_count": len(tables),
                "image_count": len(page.images or []),
            })

            logger.debug(
                f"Page {page_num}: type={page_type}, text_len={text_len}, "
                f"visual_ratio={visual_ratio:.3f}, tables={len(tables)}, images={len(page.images or [])}"
            )

    text_count = sum(1 for r in results if r["page_type"] == "text")
    visual_count = sum(1 for r in results if r["page_type"] == "visual")
    logger.info(f"Classified {len(results)} pages: {text_count} text, {visual_count} visual")

    return results
