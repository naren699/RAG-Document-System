"""Create a synthetic AI infographic PDF for testing image-only page handling.

The PDF contains a single page with an embedded image that has text rendered
INTO the image (no PDF text layer), simulating a scanned/image-only infographic.
"""
import pymupdf
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import io

OUTPUT_PATH = Path(__file__).parent.parent / "data" / "ai_infographic.pdf"

def create_infographic_image(width=2000, height=2800):
    """Create a realistic-looking AI infographic image with multiple sections."""
    img = Image.new("RGB", (width, height), "#1a1a2e")
    draw = ImageDraw.Draw(img)

    try:
        title_font = ImageFont.truetype("arial.ttf", 52)
        heading_font = ImageFont.truetype("arial.ttf", 36)
        body_font = ImageFont.truetype("arial.ttf", 24)
        small_font = ImageFont.truetype("arial.ttf", 20)
    except OSError:
        title_font = ImageFont.load_default().font_variant(size=52)
        heading_font = ImageFont.load_default().font_variant(size=36)
        body_font = ImageFont.load_default().font_variant(size=24)
        small_font = ImageFont.load_default().font_variant(size=20)

    # Title banner
    draw.rectangle([0, 0, width, 160], fill="#16213e")
    draw.text((width // 2, 50), "ARTIFICIAL INTELLIGENCE", fill="#e94560", font=title_font, anchor="mt")
    draw.text((width // 2, 110), "A Complete Overview", fill="#a8d8ea", font=heading_font, anchor="mt")

    y = 200

    # Section 1: Types of AI by Capability
    draw.rectangle([40, y, width - 40, y + 380], fill="#0f3460", outline="#e94560", width=2)
    draw.text((width // 2, y + 20), "Three Types of AI Based on Capability", fill="#e94560", font=heading_font, anchor="mt")

    col_w = (width - 120) // 3
    for i, (name, desc) in enumerate([
        ("Narrow AI", "Also called Weak AI.\nDesigned for one specific task.\nExamples: Siri, Alexa,\nimage recognition."),
        ("General AI", "Also called Strong AI.\nCan understand, learn, and\napply intelligence to any\ntask like a human."),
        ("Super AI", "Hypothetical AI that\nsurpasses human intelligence\nin all aspects including\ncreativity and wisdom."),
    ]):
        x = 60 + i * col_w
        draw.rectangle([x, y + 70, x + col_w - 20, y + 360], fill="#16213e", outline="#a8d8ea", width=1)
        draw.text((x + col_w // 2 - 10, y + 90), name, fill="#e94560", font=body_font, anchor="mt")
        for j, line in enumerate(desc.split("\n")):
            draw.text((x + 15, y + 130 + j * 28), line, fill="#ffffff", font=small_font)

    y += 410

    # Section 2: Four Types by Functionality
    draw.rectangle([40, y, width - 40, y + 380], fill="#0f3460", outline="#e94560", width=2)
    draw.text((width // 2, y + 20), "Four Types of AI Based on Functionality", fill="#e94560", font=heading_font, anchor="mt")

    col_w = (width - 120) // 2
    for i, (name, desc) in enumerate([
        ("Reactive Machines", "Cannot form memories.\nReacts to current input only.\nExample: IBM Deep Blue."),
        ("Limited Memory", "Can learn from recent data.\nUsed in self-driving cars\nand chatbots."),
        ("Theory of Mind", "Can understand emotions\nand beliefs of others.\nStill in research stage."),
        ("Self-Aware AI", "Has own consciousness\nand self-awareness.\nPurely hypothetical."),
    ]):
        row = i // 2
        col = i % 2
        x = 60 + col * col_w
        yy = y + 70 + row * 165
        draw.rectangle([x, yy, x + col_w - 20, yy + 150], fill="#16213e", outline="#a8d8ea", width=1)
        draw.text((x + 15, yy + 15), name, fill="#e94560", font=body_font)
        for j, line in enumerate(desc.split("\n")):
            draw.text((x + 15, yy + 50 + j * 26), line, fill="#ffffff", font=small_font)

    y += 410

    # Section 3: How AI Works
    draw.rectangle([40, y, width - 40, y + 280], fill="#0f3460", outline="#e94560", width=2)
    draw.text((width // 2, y + 20), "How AI Works", fill="#e94560", font=heading_font, anchor="mt")

    steps = [
        "1. Data Collection",
        "2. Data Preprocessing",
        "3. Model Training",
        "4. Evaluation",
        "5. Prediction/Inference",
    ]
    step_w = (width - 120) // len(steps)
    for i, step in enumerate(steps):
        x = 60 + i * step_w
        draw.rounded_rectangle([x, y + 80, x + step_w - 15, y + 160], radius=10, fill="#16213e", outline="#a8d8ea")
        draw.text((x + step_w // 2 - 7, y + 120), step, fill="#ffffff", font=small_font, anchor="mm")
        if i < len(steps) - 1:
            arrow_x = x + step_w - 7
            draw.text((arrow_x, y + 120), "->", fill="#e94560", font=body_font, anchor="mm")

    draw.text((60, y + 180), "Each step builds on the previous one. Data is collected, cleaned,", fill="#ffffff", font=small_font)
    draw.text((60, y + 210), "used to train a model, evaluated for accuracy, then deployed.", fill="#ffffff", font=small_font)

    y += 310

    # Section 4: Neural Network Types
    draw.rectangle([40, y, width - 40, y + 520], fill="#0f3460", outline="#e94560", width=2)
    draw.text((width // 2, y + 20), "Key Neural Network Architectures", fill="#e94560", font=heading_font, anchor="mt")

    architectures = [
        ("RNN (Recurrent Neural Network)",
         "Processes sequential data.\nHas loops for memory.\nLimitation: struggles with\nlong-term dependencies."),
        ("LSTM (Long Short-Term Memory)",
         "Improved version of RNN.\nHandles long-term dependencies\nusing gates (forget, input,\noutput) to control information."),
        ("CNN (Convolutional Neural Network)",
         "Excels at image processing.\nUses filters to detect\nfeatures like edges and\npatterns in visual data."),
        ("Transformer",
         "Uses the attention mechanism.\nProcesses all tokens in parallel.\nExamples: BERT, GPT.\nRevolutionized NLP tasks."),
    ]

    col_w = (width - 120) // 2
    for i, (name, desc) in enumerate(architectures):
        row = i // 2
        col = i % 2
        x = 60 + col * col_w
        yy = y + 70 + row * 220
        draw.rectangle([x, yy, x + col_w - 20, yy + 200], fill="#16213e", outline="#a8d8ea", width=1)
        draw.text((x + 15, yy + 15), name, fill="#e94560", font=body_font)
        for j, line in enumerate(desc.split("\n")):
            draw.text((x + 15, yy + 55 + j * 28), line, fill="#ffffff", font=small_font)

    y += 550

    # Section 5: small footer
    draw.rectangle([0, y, width, y + 60], fill="#16213e")
    draw.text((width // 2, y + 30), "AI Infographic 2024 - Educational Overview", fill="#a8d8ea", font=small_font, anchor="mm")

    return img


def create_pdf(img: Image.Image, output_path: Path):
    """Create a PDF with the image embedded (no text layer)."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    doc = pymupdf.open()
    img_width, img_height = img.size
    page_w = img_width * 72 / 150
    page_h = img_height * 72 / 150
    page = doc.new_page(width=page_w, height=page_h)

    rect = pymupdf.Rect(0, 0, page_w, page_h)
    page.insert_image(rect, stream=buf.getvalue())

    doc.save(str(output_path))
    doc.close()
    print(f"Created: {output_path} ({output_path.stat().st_size / 1024:.1f} KB)")
    print(f"  Image size: {img.size[0]}x{img.size[1]}px")
    print(f"  PDF page size: {page_w:.0f}x{page_h:.0f}pt")


if __name__ == "__main__":
    print("Creating AI infographic image...")
    img = create_infographic_image()
    print(f"Image created: {img.size[0]}x{img.size[1]}px")

    print("\nCreating PDF (image-only, no text layer)...")
    create_pdf(img, OUTPUT_PATH)
    print("\nDone. Run diagnose_pdf.py on it to see the root cause.")
