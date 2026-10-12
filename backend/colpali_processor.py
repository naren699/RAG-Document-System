import pymupdf
import torch
import logging
import os
import numpy as np
from pathlib import Path
from PIL import Image

logger = logging.getLogger(__name__)

_model = None
_processor = None
COLPALI_MODEL = os.getenv("COLPALI_MODEL", "vidore/colpali-v1.2")
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
PAGE_IMAGES_DIR = Path("page_images")


def get_model():
    global _model, _processor
    if _model is None:
        from colpali_engine import ColPali, ColPaliProcessor

        logger.info(f"Loading ColPali model: {COLPALI_MODEL} on {DEVICE}")
        _model = ColPali.from_pretrained(
            COLPALI_MODEL,
            torch_dtype=torch.float32,
            device_map=DEVICE,
        ).eval()
        _processor = ColPaliProcessor.from_pretrained(COLPALI_MODEL)
        logger.info("ColPali model loaded")
    return _model, _processor


def render_page_as_image(pdf_path: str, page_num: int, dpi: int = 150) -> Image.Image:
    """Render a single PDF page as a PIL Image."""
    doc = pymupdf.open(pdf_path)
    page = doc[page_num - 1]
    zoom = dpi / 72
    mat = pymupdf.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    doc.close()
    return img


def save_page_image(img: Image.Image, doc_id: str, page_num: int) -> str:
    """Save a page image and return its path."""
    PAGE_IMAGES_DIR.mkdir(exist_ok=True)
    filename = f"{doc_id}_page_{page_num}.png"
    path = PAGE_IMAGES_DIR / filename
    img.save(str(path))
    return str(path)


def embed_page_image(img: Image.Image) -> list[float]:
    """Embed a page image using ColPali, returning a single averaged vector."""
    model, processor = get_model()

    with torch.no_grad():
        inputs = processor.process_images([img]).to(DEVICE)
        embeddings = model(**inputs)
        page_embedding = embeddings[0].mean(dim=0).cpu().numpy()

    return page_embedding.tolist()


def embed_query_colpali(query: str) -> list[float]:
    """Embed a text query using ColPali's query encoder."""
    model, processor = get_model()

    with torch.no_grad():
        inputs = processor.process_queries([query]).to(DEVICE)
        embeddings = model(**inputs)
        query_embedding = embeddings[0].mean(dim=0).cpu().numpy()

    return query_embedding.tolist()


def process_visual_pages(
    pdf_path: str,
    visual_pages: list[dict],
    doc_id: str,
) -> list[dict]:
    """Process visual pages through ColPali and return chunks with embeddings.

    Each visual page becomes one 'chunk' with its ColPali embedding.
    """
    if not visual_pages:
        return [], []

    chunks = []
    embeddings = []

    for page_info in visual_pages:
        page_num = page_info["page_num"]
        logger.info(f"Processing visual page {page_num} with ColPali")

        img = render_page_as_image(pdf_path, page_num)
        image_path = save_page_image(img, doc_id, page_num)
        embedding = embed_page_image(img)

        chunks.append({
            "chunk_id": f"{doc_id}_visual_page_{page_num}",
            "doc_id": doc_id,
            "page_num": page_num,
            "text": f"[Visual content from page {page_num}]",
            "token_count": 0,
            "source": f"{doc_id}, page {page_num} (visual)",
            "page_type": "visual",
            "image_path": image_path,
        })
        embeddings.append(embedding)

    logger.info(f"Processed {len(chunks)} visual pages for {doc_id}")
    return chunks, embeddings
