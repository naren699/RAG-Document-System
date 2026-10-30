from unittest.mock import patch, MagicMock
from page_classifier import classify_pages


def _make_mock_page(text="", images=None, tables=None, table_bboxes=None, width=612, height=792):
    page = MagicMock()
    page.width = width
    page.height = height
    page.extract_text.return_value = text
    page.images = images or []
    page.extract_tables.return_value = tables or []
    table_objs = []
    for bbox in (table_bboxes or []):
        t = MagicMock()
        t.bbox = bbox
        table_objs.append(t)
    page.find_tables.return_value = table_objs
    return page


def _mock_pdf_with_pages(pages):
    mock_pdf = MagicMock()
    mock_pdf.pages = pages
    mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
    mock_pdf.__exit__ = MagicMock(return_value=False)
    return mock_pdf


@patch("page_classifier.pdfplumber.open")
def test_classify_text_page(mock_open):
    page = _make_mock_page(
        text="A " * 500,
        images=[{"x0": 0, "x1": 10, "top": 0, "bottom": 10}],
    )
    mock_open.return_value = _mock_pdf_with_pages([page])
    results = classify_pages("fake.pdf")
    assert len(results) == 1
    assert results[0]["page_type"] == "text"
    assert results[0]["visual_ratio"] < 0.50


@patch("page_classifier.pdfplumber.open")
def test_classify_visual_page(mock_open):
    page = _make_mock_page(
        text="Short",
        images=[{"x0": 0, "x1": 500, "top": 0, "bottom": 630}],
    )
    mock_open.return_value = _mock_pdf_with_pages([page])
    results = classify_pages("fake.pdf")
    assert len(results) == 1
    assert results[0]["page_type"] == "visual"
    assert results[0]["visual_ratio"] > 0.50


@patch("page_classifier.pdfplumber.open")
def test_classify_low_text_high_visual(mock_open):
    page_area = 612 * 792
    target_ratio = 0.20
    img_area = target_ratio * page_area
    img_side = img_area ** 0.5
    page = _make_mock_page(
        text="x" * 30,
        images=[{"x0": 0, "x1": img_side, "top": 0, "bottom": img_side}],
    )
    mock_open.return_value = _mock_pdf_with_pages([page])
    results = classify_pages("fake.pdf")
    assert results[0]["page_type"] == "visual"
    assert results[0]["text_length"] == 30


@patch("page_classifier.pdfplumber.open")
def test_classify_empty_page(mock_open):
    page = _make_mock_page(text="", images=[], tables=[])
    mock_open.return_value = _mock_pdf_with_pages([page])
    results = classify_pages("fake.pdf")
    assert results[0]["page_type"] == "text"
    assert results[0]["visual_ratio"] == 0
    assert results[0]["text_length"] == 0


@patch("page_classifier.pdfplumber.open")
def test_classify_boundary(mock_open):
    page_area = 612 * 792
    target_ratio = 0.50
    img_area = target_ratio * page_area
    img_side = img_area ** 0.5
    page = _make_mock_page(
        text="A " * 200,
        images=[{"x0": 0, "x1": img_side, "top": 0, "bottom": img_side}],
    )
    mock_open.return_value = _mock_pdf_with_pages([page])
    results = classify_pages("fake.pdf")
    assert results[0]["page_type"] == "text"


@patch("page_classifier.pdfplumber.open")
def test_classify_returns_all_fields(mock_open):
    page = _make_mock_page(text="Hello world")
    mock_open.return_value = _mock_pdf_with_pages([page])
    results = classify_pages("fake.pdf")
    expected_keys = {
        "page_num", "page_type", "text_length", "visual_ratio",
        "has_tables", "has_images", "table_count", "image_count",
    }
    assert set(results[0].keys()) == expected_keys
