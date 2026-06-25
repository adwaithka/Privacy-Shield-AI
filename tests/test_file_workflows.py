import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import fitz
import pytesseract
from docx import Document
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from extractor import extract_text
from redactor import produce_redacted_file


def tesseract_available():
    try:
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def fixture_font(size=32):
    try:
        return ImageFont.truetype(r"C:\Windows\Fonts\arial.ttf", size)
    except Exception:
        return ImageFont.load_default()


class FileWorkflowTests(unittest.TestCase):
    def test_txt_extraction(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sample.txt"
            path.write_text("Email: user@example.com", encoding="utf-8")

            self.assertIn("user@example.com", extract_text(str(path)))

    def test_docx_extraction(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sample.docx"
            doc = Document()
            doc.add_paragraph("Employee ID: EMP-12345")
            doc.save(path)

            self.assertIn("EMP-12345", extract_text(str(path)))

    def test_native_pdf_extraction(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "native.pdf"
            pdf = canvas.Canvas(str(path), pagesize=letter)
            pdf.drawString(72, 720, "Name: Rahul Sharma")
            pdf.save()

            self.assertIn("Rahul Sharma", extract_text(str(path)))

    @unittest.skipUnless(tesseract_available(), "Tesseract OCR is not available")
    def test_image_ocr_extraction(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "image.png"
            img = Image.new("RGB", (500, 120), "white")
            ImageDraw.Draw(img).text((20, 40), "Phone: 9876543210", fill="black", font=fixture_font())
            img.save(path)

            self.assertIn("9876543210", extract_text(str(path)))

    @unittest.skipUnless(tesseract_available(), "Tesseract OCR is not available")
    def test_scanned_pdf_ocr_extraction(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "scan.png"
            pdf_path = Path(tmpdir) / "scan.pdf"
            img = Image.new("RGB", (800, 220), "white")
            ImageDraw.Draw(img).text((40, 80), "Email: scan@example.com", fill="black", font=fixture_font())
            img.save(image_path)
            Image.open(image_path).save(pdf_path, "PDF")

            self.assertIn("scan@example.com", extract_text(str(pdf_path)))

    @unittest.skipUnless(tesseract_available(), "Tesseract OCR is not available")
    def test_visual_pdf_redaction_smoke(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "native.pdf"
            pdf = canvas.Canvas(str(path), pagesize=letter)
            pdf.drawString(72, 720, "Email: redact@example.com")
            pdf.save()

            redacted = produce_redacted_file(
                file_path=str(path),
                extracted_text="Email: redact@example.com",
                masked_text="Email: <EMAIL_ADDRESS>",
                entities=[{"type": "EMAIL_ADDRESS", "text": "redact@example.com", "score": 1.0}],
                results=[],
                original_filename="native.pdf",
            )

            out_path = Path(tmpdir) / "redacted.pdf"
            out_path.write_bytes(redacted)
            doc = fitz.open(out_path)
            try:
                self.assertNotIn("redact@example.com", "\n".join(page.get_text() for page in doc))
            finally:
                doc.close()


if __name__ == "__main__":
    unittest.main()
