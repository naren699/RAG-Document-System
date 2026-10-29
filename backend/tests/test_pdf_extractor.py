import pytest
from pdf_extractor import extract_text_from_pdf


class TestExtractValidation:
    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            extract_text_from_pdf("/nonexistent/path/file.pdf")

    def test_not_a_pdf(self, tmp_path):
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("not a pdf")
        with pytest.raises(ValueError, match="Not a PDF"):
            extract_text_from_pdf(str(txt_file))
