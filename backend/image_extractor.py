"""Extract text from visual/image-only PDF pages using OCR and vision LLM.

Orchestrates: page rendering, tiling, OCR, vision fallback, merge, and caching.
Extracted text feeds into the standard chunk_document() pipeline.
"""
import hashlib
import json
import logging
import os
import time
from pathlib import Path

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

RENDER_DPI = 250
TILE_SIZE = 1024
TILE_OVERLAP = 128
CACHE_DIR = Path("page_images/.cache")
TILE_DIR = Path("page_images/tiles")

OCR_MIN_CONFIDENCE = 0.55
OCR_MIN_CHARS = 30
OCR_MIN_BLOCKS = 2

VISION_LLM_ENABLED = os.getenv("VISION_LLM_ENABLED", "true").lower() == "true"
VISION_LLM_MAX_PAGES = int(os.getenv("VISION_LLM_MAX_PAGES", "10"))

_ocr_reader = None


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

def _file_hash(pdf_path: str) -> str:
    with open(pdf_path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()[:12]


def _get_cached(pdf_path: str, page_num: int) -> dict | None:
    key = f"{_file_hash(pdf_path)}_p{page_num}"
    cache_file = CACHE_DIR / f"{key}.json"
    if cache_file.exists():
        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            logger.info(f"Cache hit for page {page_num} (method={data.get('method')})")
            return data
        except Exception:
            return None
    return None


def _save_cache(pdf_path: str, page_num: int, text: str, method: str, confidence: float):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = f"{_file_hash(pdf_path)}_p{page_num}"
    cache_file = CACHE_DIR / f"{key}.json"
    cache_file.write_text(json.dumps({
        "text": text,
        "method": method,
        "confidence": confidence,
    }, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# OCR
# ---------------------------------------------------------------------------

def get_ocr_reader():
    global _ocr_reader
    if _ocr_reader is None:
        import easyocr
        logger.info("Loading EasyOCR reader (English, CPU)...")
        start = time.time()
        _ocr_reader = easyocr.Reader(["en"], gpu=False, verbose=False)
        logger.info(f"EasyOCR reader loaded in {int((time.time() - start) * 1000)}ms")
    return _ocr_reader


def ocr_image(img: Image.Image) -> dict:
    """Run OCR on a single image. Returns {text, blocks, avg_confidence, total_chars}."""
    reader = get_ocr_reader()
    img_array = np.array(img)
    results = reader.readtext(img_array)

    blocks = []
    for bbox, text, confidence in results:
        blocks.append({"text": text, "confidence": confidence, "bbox": bbox})

    all_text = " ".join(b["text"] for b in blocks)
    confidences = [b["confidence"] for b in blocks]
    avg_conf = sum(confidences) / len(confidences) if confidences else 0.0

    return {
        "text": all_text,
        "blocks": blocks,
        "avg_confidence": round(avg_conf, 4),
        "total_chars": len(all_text),
    }


def _offset_bbox(bbox, dx: int, dy: int):
    return [[pt[0] + dx, pt[1] + dy] for pt in bbox]


def _bbox_center(bbox):
    xs = [pt[0] for pt in bbox]
    ys = [pt[1] for pt in bbox]
    return (sum(xs) / len(xs), sum(ys) / len(ys))


def merge_tile_ocr_results(tile_results: list[dict], tiles: list[dict]) -> dict:
    """Merge OCR from multiple tiles into one page-level result, deduplicating overlaps."""
    all_blocks = []

    for tile_info, ocr_result in zip(tiles, tile_results):
        for block in ocr_result["blocks"]:
            abs_bbox = _offset_bbox(block["bbox"], tile_info["x0"], tile_info["y0"])
            cx, cy = _bbox_center(abs_bbox)
            all_blocks.append({
                "text": block["text"],
                "confidence": block["confidence"],
                "center_x": cx,
                "center_y": cy,
            })

    dedup_dist = TILE_OVERLAP * 0.6
    deduped = []
    for block in all_blocks:
        is_dup = False
        for i, existing in enumerate(deduped):
            if (abs(block["center_x"] - existing["center_x"]) < dedup_dist
                    and abs(block["center_y"] - existing["center_y"]) < dedup_dist):
                if block["confidence"] > existing["confidence"]:
                    deduped[i] = block
                is_dup = True
                break
        if not is_dup:
            deduped.append(block)

    line_tolerance = 15
    deduped.sort(key=lambda b: (round(b["center_y"] / line_tolerance), b["center_x"]))

    merged_text = " ".join(b["text"] for b in deduped)
    confidences = [b["confidence"] for b in deduped]
    avg_conf = sum(confidences) / len(confidences) if confidences else 0.0

    return {
        "text": merged_text,
        "blocks": deduped,
        "avg_confidence": round(avg_conf, 4),
        "total_chars": len(merged_text),
        "block_count": len(deduped),
    }


def is_ocr_poor(ocr_result: dict) -> bool:
    """Determine if OCR output is too low quality to use."""
    if ocr_result["total_chars"] < OCR_MIN_CHARS:
        return True
    if ocr_result["avg_confidence"] < OCR_MIN_CONFIDENCE:
        return True
    block_count = ocr_result.get("block_count", len(ocr_result.get("blocks", [])))
    if block_count < OCR_MIN_BLOCKS:
        return True
    return False


# ---------------------------------------------------------------------------
# Tiling
# ---------------------------------------------------------------------------

def split_into_tiles(img: Image.Image) -> list[dict]:
    """Split a large image into overlapping tiles in row-major (reading) order."""
    w, h = img.size
    if w <= TILE_SIZE * 1.5 and h <= TILE_SIZE * 1.5:
        return [{"tile": img, "row": 0, "col": 0,
                 "x0": 0, "y0": 0, "x1": w, "y1": h}]

    stride = TILE_SIZE - TILE_OVERLAP
    tiles = []
    row = 0
    y = 0
    while y < h:
        col = 0
        x = 0
        y1 = min(y + TILE_SIZE, h)
        while x < w:
            x1 = min(x + TILE_SIZE, w)
            tile = img.crop((x, y, x1, y1))
            tiles.append({
                "tile": tile, "row": row, "col": col,
                "x0": x, "y0": y, "x1": x1, "y1": y1,
            })
            x += stride
            col += 1
            if x1 == w:
                break
        y += stride
        row += 1
        if y1 == h:
            break

    logger.info(f"Split {w}x{h}px image into {len(tiles)} tiles "
                f"({row} rows x {col + 1} cols, tile={TILE_SIZE}px, overlap={TILE_OVERLAP}px)")
    return tiles


def save_tiles(tiles: list[dict], doc_id: str, page_num: int) -> list[str]:
    """Save tile images to disk. Returns list of file paths."""
    TILE_DIR.mkdir(parents=True, exist_ok=True)
    paths = []
    for t in tiles:
        filename = f"{doc_id}_p{page_num}_r{t['row']}_c{t['col']}.png"
        path = TILE_DIR / filename
        t["tile"].save(str(path))
        paths.append(str(path))
    return paths


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def extract_visual_pages(
    pdf_path: str,
    visual_pages: list[dict],
    doc_id: str,
    use_vision: bool | None = None,
) -> dict:
    """Extract text from visual pages using OCR and optionally vision LLM fallback.

    Args:
        use_vision: Override for VISION_LLM_ENABLED. None = use env default.

    Returns {
        chunks: list[dict],
        warnings: list[str],
        ocr_page_count: int,
        vision_page_count: int,
        methods_used: list[str],
    }
    """
    from colpali_processor import render_page_as_image, save_page_image
    from chunker import chunk_document

    vision_enabled = use_vision if use_vision is not None else VISION_LLM_ENABLED
    max_vision_pages = VISION_LLM_MAX_PAGES

    warnings = []
    extracted_pages = []
    ocr_count = 0
    vision_count = 0
    methods = set()
    vision_used = False

    for page_info in visual_pages:
        page_num = page_info["page_num"]
        logger.info(f"Processing visual page {page_num}: rendering at {RENDER_DPI} DPI")

        try:
            img = render_page_as_image(pdf_path, page_num, dpi=RENDER_DPI)
            image_path = save_page_image(img, doc_id, page_num)
        except Exception as e:
            logger.error(f"Failed to render page {page_num}: {e}")
            warnings.append(f"Could not render page {page_num}: {e}")
            continue

        # --- Check cache ---
        cached = _get_cached(pdf_path, page_num)
        if cached and cached.get("text", "").strip():
            extracted_pages.append({
                "page_num": page_num,
                "text": cached["text"],
                "has_text": True,
                "extraction_method": cached.get("method", "ocr"),
                "confidence": cached.get("confidence", 1.0),
                "image_path": image_path,
            })
            methods.add(cached.get("method", "ocr"))
            if cached.get("method") == "vision":
                vision_count += 1
            else:
                ocr_count += 1
            continue

        tiles = split_into_tiles(img)
        save_tiles(tiles, doc_id, page_num)

        # --- OCR ---
        logger.info(f"Page {page_num}: running OCR on {len(tiles)} tile(s)...")
        ocr_start = time.time()

        if len(tiles) == 1:
            ocr_result = ocr_image(img)
        else:
            tile_results = [ocr_image(t["tile"]) for t in tiles]
            ocr_result = merge_tile_ocr_results(tile_results, tiles)

        ocr_ms = int((time.time() - ocr_start) * 1000)
        logger.info(
            f"Page {page_num} OCR: {ocr_result['total_chars']} chars, "
            f"{ocr_result.get('block_count', len(ocr_result.get('blocks', [])))} blocks, "
            f"avg_confidence={ocr_result['avg_confidence']:.3f}, {ocr_ms}ms"
        )

        text = ocr_result["text"]
        confidence = ocr_result["avg_confidence"]
        extraction_method = "ocr"
        poor = is_ocr_poor(ocr_result)

        # --- Vision LLM fallback ---
        if poor and vision_enabled and vision_count < max_vision_pages:
            logger.info(f"Page {page_num}: OCR quality is poor "
                        f"(chars={ocr_result['total_chars']}, conf={confidence:.3f}), "
                        f"trying vision LLM...")
            try:
                from llm_provider import transcribe_page_with_vision
                vision_result = transcribe_page_with_vision(img, page_num)
                vision_text = vision_result.get("text", "").strip()
                if vision_text and len(vision_text) > 20 and "[Blank page]" not in vision_text:
                    text = vision_text
                    extraction_method = "vision"
                    confidence = 1.0
                    vision_count += 1
                    vision_used = True
                    logger.info(f"Page {page_num}: vision LLM returned {len(text)} chars, "
                                f"{vision_result.get('generation_time_ms', 0)}ms, "
                                f"cost=${vision_result.get('estimated_cost_usd', 0)}")
                else:
                    logger.info(f"Page {page_num}: vision LLM returned insufficient text, using OCR")
            except Exception as e:
                logger.warning(f"Page {page_num}: vision LLM failed: {e}, using OCR fallback")
                warnings.append(f"Vision LLM failed for page {page_num}, using OCR fallback")
        elif poor and vision_enabled and vision_count >= max_vision_pages:
            warnings.append(
                f"Page {page_num}: OCR quality is poor but vision LLM page cap "
                f"({max_vision_pages}) reached, using OCR"
            )

        if extraction_method == "ocr":
            ocr_count += 1
        methods.add(extraction_method)

        # --- Cache ---
        if text and text.strip():
            _save_cache(pdf_path, page_num, text.strip(), extraction_method, confidence)

        extracted_pages.append({
            "page_num": page_num,
            "text": text.strip() if text else "",
            "has_text": bool(text and text.strip()),
            "extraction_method": extraction_method,
            "confidence": confidence,
            "image_path": image_path,
        })

    # --- Privacy warning ---
    if vision_used:
        warnings.append(
            "Page images were sent to the external LLM for transcription. "
            "This may expose sensitive visual content."
        )

    # --- Chunk using the standard chunker ---
    pages_with_text = [p for p in extracted_pages if p["has_text"]]
    if not pages_with_text:
        return {
            "chunks": [],
            "warnings": warnings,
            "ocr_page_count": ocr_count,
            "vision_page_count": vision_count,
            "methods_used": list(methods),
        }

    raw_chunks = chunk_document(pages_with_text, doc_id)

    page_metadata = {p["page_num"]: p for p in extracted_pages}
    for chunk in raw_chunks:
        pm = page_metadata.get(chunk["page_num"], {})
        chunk["page_type"] = "visual"
        chunk["extraction_method"] = pm.get("extraction_method", "ocr")
        chunk["confidence"] = pm.get("confidence", 0.0)
        chunk["image_path"] = pm.get("image_path", "")

    return {
        "chunks": raw_chunks,
        "warnings": warnings,
        "ocr_page_count": ocr_count,
        "vision_page_count": vision_count,
        "methods_used": list(methods),
    }
