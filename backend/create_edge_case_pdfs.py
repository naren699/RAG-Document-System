#!/usr/bin/env python3
"""Create edge case test PDFs for Step 9 testing.

Run: python create_edge_case_pdfs.py
"""
import io
from pathlib import Path

from PIL import Image
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

TEST_DIR = Path("test_files")


def create_scanned_multipage_pdf():
    """Create a multi-page PDF where all pages are scanned images (no selectable text)."""
    output_path = TEST_DIR / "edge_case_scanned.pdf"

    c = canvas.Canvas(str(output_path), pagesize=letter)
    width, height = letter

    for page_num in range(1, 4):
        img = Image.new("RGB", (800, 600), color=(245, 245, 245))
        from PIL import ImageDraw, ImageFont
        draw = ImageDraw.Draw(img)

        try:
            font = ImageFont.truetype("arial.ttf", 24)
            font_small = ImageFont.truetype("arial.ttf", 16)
        except:
            font = ImageFont.load_default()
            font_small = font

        draw.text((50, 50), f"SCANNED DOCUMENT - PAGE {page_num}", fill="black", font=font)
        draw.text((50, 100), "This page simulates a scanned document.", fill="gray", font=font_small)
        draw.text((50, 130), "The text is embedded as an image, not selectable.", fill="gray", font=font_small)
        draw.text((50, 180), f"Content on page {page_num}:", fill="black", font=font_small)
        draw.text((70, 210), f"- Item A on page {page_num}", fill="black", font=font_small)
        draw.text((70, 240), f"- Item B on page {page_num}", fill="black", font=font_small)
        draw.text((70, 270), f"- Item C on page {page_num}", fill="black", font=font_small)

        img_buffer = io.BytesIO()
        img.save(img_buffer, format="PNG")
        img_buffer.seek(0)

        c.drawImage(ImageReader(img_buffer), 0, 0, width=width, height=height)
        if page_num < 3:
            c.showPage()

    c.save()
    print(f"Created: {output_path}")
    return output_path


def create_mixed_text_chart_pdf():
    """Create a PDF with text pages and a chart image page."""
    output_path = TEST_DIR / "edge_case_mixed.pdf"

    c = canvas.Canvas(str(output_path), pagesize=letter)
    width, height = letter

    c.setFont("Helvetica-Bold", 24)
    c.drawString(72, height - 72, "Mixed Content Document")
    c.setFont("Helvetica", 12)
    c.drawString(72, height - 110, "Page 1: This is a normal text page with selectable content.")
    c.drawString(72, height - 130, "The RAG system should extract this text using the text layer.")
    c.drawString(72, height - 160, "Key information:")
    c.drawString(90, height - 185, "- Annual revenue: $1.5 million")
    c.drawString(90, height - 205, "- Employee count: 50")
    c.drawString(90, height - 225, "- Founded: 2020")
    c.showPage()

    img = Image.new("RGB", (800, 600), color="white")
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)

    draw.rectangle([50, 50, 750, 550], outline="black", width=2)
    draw.text((350, 60), "Sales Chart 2024", fill="black")

    bar_data = [("Q1", 100), ("Q2", 150), ("Q3", 200), ("Q4", 180)]
    bar_width = 80
    max_val = max(d[1] for d in bar_data)
    for i, (label, value) in enumerate(bar_data):
        x = 120 + i * (bar_width + 40)
        bar_height = int((value / max_val) * 300)
        draw.rectangle([x, 500 - bar_height, x + bar_width, 500], fill="steelblue")
        draw.text((x + 20, 510), label, fill="black")
        draw.text((x + 20, 490 - bar_height - 20), str(value), fill="black")

    img_buffer = io.BytesIO()
    img.save(img_buffer, format="PNG")
    img_buffer.seek(0)

    c.drawImage(ImageReader(img_buffer), 0, 0, width=width, height=height)
    c.showPage()

    c.setFont("Helvetica-Bold", 18)
    c.drawString(72, height - 72, "Page 3: Conclusion")
    c.setFont("Helvetica", 12)
    c.drawString(72, height - 110, "The chart on page 2 shows quarterly sales performance.")
    c.drawString(72, height - 130, "Q3 had the highest sales at $200K.")
    c.drawString(72, height - 150, "Overall trend is positive with 80% growth Q1 to Q3.")

    c.save()
    print(f"Created: {output_path}")
    return output_path


def create_blank_page_pdf():
    """Create a PDF with a blank page in the middle."""
    output_path = TEST_DIR / "edge_case_blank.pdf"

    c = canvas.Canvas(str(output_path), pagesize=letter)
    width, height = letter

    c.setFont("Helvetica-Bold", 18)
    c.drawString(72, height - 72, "Document with Blank Page")
    c.setFont("Helvetica", 12)
    c.drawString(72, height - 110, "Page 1 contains content.")
    c.drawString(72, height - 130, "Page 2 will be completely blank.")
    c.drawString(72, height - 150, "Page 3 contains more content.")
    c.showPage()

    c.showPage()

    c.setFont("Helvetica-Bold", 18)
    c.drawString(72, height - 72, "Page 3: Final Content")
    c.setFont("Helvetica", 12)
    c.drawString(72, height - 110, "This page appears after the blank page.")
    c.drawString(72, height - 130, "The system should handle blank pages gracefully.")

    c.save()
    print(f"Created: {output_path}")
    return output_path


def create_large_image_pdf():
    """Create a PDF with a very large (4K) image."""
    output_path = TEST_DIR / "edge_case_large.pdf"

    img = Image.new("RGB", (3840, 2160), color=(240, 240, 250))
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)

    draw.rectangle([100, 100, 3740, 2060], outline="navy", width=5)
    draw.text((200, 200), "HIGH RESOLUTION DOCUMENT (4K)", fill="navy")
    draw.text((200, 300), "This image is 3840x2160 pixels", fill="gray")
    draw.text((200, 400), "Testing large image handling and tiling", fill="gray")

    for i in range(5):
        for j in range(3):
            x = 200 + i * 700
            y = 600 + j * 400
            draw.rectangle([x, y, x + 600, y + 300], outline="steelblue", width=2)
            draw.text((x + 50, y + 50), f"Section {i+1}-{j+1}", fill="steelblue")
            draw.text((x + 50, y + 100), f"Content block {i*3+j+1}", fill="gray")

    img_buffer = io.BytesIO()
    img.save(img_buffer, format="PNG")
    img_buffer.seek(0)

    c = canvas.Canvas(str(output_path), pagesize=letter)
    width, height = letter
    c.drawImage(ImageReader(img_buffer), 0, 0, width=width, height=height, preserveAspectRatio=True)
    c.save()

    print(f"Created: {output_path}")
    return output_path


def create_password_protected_pdf():
    """Create a note about password-protected PDFs (requires PyPDF2)."""
    output_path = TEST_DIR / "edge_case_protected.pdf"

    try:
        from pypdf import PdfWriter, PdfReader
        import io as io_module

        temp_buffer = io_module.BytesIO()
        c = canvas.Canvas(temp_buffer, pagesize=letter)
        c.setFont("Helvetica-Bold", 18)
        c.drawString(72, letter[1] - 72, "Protected Document")
        c.setFont("Helvetica", 12)
        c.drawString(72, letter[1] - 110, "This document is password protected.")
        c.drawString(72, letter[1] - 130, "Password: test123")
        c.save()

        temp_buffer.seek(0)
        reader = PdfReader(temp_buffer)
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)

        writer.encrypt("test123")

        with open(output_path, "wb") as f:
            writer.write(f)

        print(f"Created: {output_path} (password: test123)")
    except ImportError:
        print(f"SKIP: {output_path} - pypdf not installed")
        c = canvas.Canvas(str(output_path), pagesize=letter)
        c.setFont("Helvetica", 12)
        c.drawString(72, letter[1] - 72, "Note: This should be a password-protected PDF.")
        c.drawString(72, letter[1] - 92, "Install pypdf to create actual protected PDF.")
        c.save()
        print(f"Created placeholder: {output_path}")

    return output_path


def main():
    TEST_DIR.mkdir(exist_ok=True)
    print(f"Creating edge case test PDFs in {TEST_DIR}/\n")

    create_scanned_multipage_pdf()
    create_mixed_text_chart_pdf()
    create_blank_page_pdf()
    create_large_image_pdf()
    create_password_protected_pdf()

    print("\nAll edge case PDFs created!")
    print(f"\nRun edge case tests with:")
    print(f"  python test_visual_extraction.py --edge-cases")


if __name__ == "__main__":
    main()
