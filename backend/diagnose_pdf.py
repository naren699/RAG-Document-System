"""Step 1 diagnostic: analyze a PDF to show exactly why image-only pages are rejected.

Usage: python -I diagnose_pdf.py <path_to_pdf>
"""
import sys
import pdfplumber
import pymupdf
from pathlib import Path

def diagnose(pdf_path: str):
    path = Path(pdf_path)
    if not path.exists():
        print(f"ERROR: File not found: {pdf_path}")
        return

    print(f"=== Diagnosing: {path.name} ===\n")

    # --- pdfplumber analysis (same lib used by page_classifier + pdf_extractor) ---
    print("--- pdfplumber analysis (text extraction + page classification) ---")
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            page_num = i + 1
            page_area = page.width * page.height

            text = page.extract_text() or ""
            text_len = len(text.strip())

            images = page.images or []
            image_area = 0
            for img in images:
                w = abs(img.get("x1", 0) - img.get("x0", 0))
                h = abs(img.get("bottom", 0) - img.get("top", 0))
                image_area += w * h

            tables = page.extract_tables() or []
            table_objs = page.find_tables() or []
            table_area = 0
            for t in table_objs:
                bbox = t.bbox
                table_area += abs(bbox[2] - bbox[0]) * abs(bbox[3] - bbox[1])

            visual_area = image_area + table_area
            visual_ratio = visual_area / page_area if page_area > 0 else 0

            is_visual = visual_ratio > 0.50 or (text_len < 50 and visual_ratio > 0.15)
            page_type = "visual" if is_visual else "text"
            has_text = bool(text.strip())

            print(f"\n  Page {page_num}:")
            print(f"    Characters extracted:  {text_len}")
            print(f"    has_text:              {has_text}")
            print(f"    Images found:          {len(images)}")
            print(f"    Image area ratio:      {(image_area / page_area * 100):.1f}% of page")
            print(f"    Tables found:          {len(tables)}")
            print(f"    Visual ratio:          {visual_ratio:.3f}")
            print(f"    Classification:        {page_type}")

            if images:
                print(f"    Image details:")
                for j, img in enumerate(images):
                    w = abs(img.get("x1", 0) - img.get("x0", 0))
                    h = abs(img.get("bottom", 0) - img.get("top", 0))
                    print(f"      [{j+1}] size={w:.0f}x{h:.0f}pt, name={img.get('name', 'N/A')}")

            if text_len > 0 and text_len <= 200:
                print(f"    Text preview: {repr(text.strip()[:200])}")

    # --- PyMuPDF analysis (image objects at PDF level) ---
    print("\n--- PyMuPDF analysis (embedded image objects) ---")
    doc = pymupdf.open(pdf_path)
    for i, page in enumerate(doc):
        page_num = i + 1
        img_list = page.get_images(full=True)
        print(f"\n  Page {page_num}: {len(img_list)} embedded image object(s)")
        for j, img_info in enumerate(img_list):
            xref = img_info[0]
            width = img_info[2]
            height = img_info[3]
            colorspace = img_info[5]
            bpc = img_info[4]
            print(f"    [{j+1}] xref={xref}, size={width}x{height}px, colorspace={colorspace}, bpc={bpc}")
    doc.close()

    # --- Ingestion simulation ---
    print("\n--- Ingestion simulation ---")
    print("  The ingestion flow in app.py would:")
    with pdfplumber.open(pdf_path) as pdf:
        all_visual = True
        any_has_text = False
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            text_len = len(text.strip())
            images = page.images or []
            image_area = sum(
                abs(img.get("x1", 0) - img.get("x0", 0)) * abs(img.get("bottom", 0) - img.get("top", 0))
                for img in images
            )
            page_area = page.width * page.height
            visual_ratio = image_area / page_area if page_area > 0 else 0
            is_visual = visual_ratio > 0.50 or (text_len < 50 and visual_ratio > 0.15)
            has_text = bool(text.strip())

            if not is_visual:
                all_visual = False
            if has_text:
                any_has_text = True

            status = "SKIPPED" if is_visual and not has_text else "OK"
            print(f"    Page {i+1}: type={'visual' if is_visual else 'text'}, has_text={has_text} -> {status}")

    colpali = False  # COLPALI_ENABLED=false
    if all_visual and not any_has_text and not colpali:
        print("\n  RESULT: all_chunks would be EMPTY")
        print("  -> HTTP 400: 'No content could be extracted from the PDF'")
        print("\n  Root cause: Every page is classified as 'visual' with has_text=False.")
        print("  The visual fallback (app.py:161-163) requires has_text=True, which fails.")
        print("  ColPali is disabled, so there is no image extraction path.")
    else:
        print("\n  RESULT: Some chunks would be created (text pages exist or have text layer)")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -I diagnose_pdf.py <path_to_pdf>")
        sys.exit(1)
    diagnose(sys.argv[1])
