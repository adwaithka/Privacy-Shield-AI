import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image

import redactor


class RedactorTests(unittest.TestCase):
    def test_entity_tokens_split_email_and_address_words(self):
        tokens = redactor._tokens_for_entity("rahul.sharma@example.com")

        self.assertIn("rahul", tokens)
        self.assertIn("sharma", tokens)
        self.assertIn("example", tokens)

    def test_find_bboxes_returns_individual_ocr_word_boxes(self):
        word_index = {
            "flat": [(10, 10, 40, 25)],
            "12": [(45, 10, 60, 25)],
            "bengaluru": [(10, 35, 80, 50)],
        }

        found = redactor._find_bboxes(word_index, "Flat 12\nBengaluru")

        self.assertEqual(set(found), {(10, 10, 40, 25), (45, 10, 60, 25), (10, 35, 80, 50)})

    def test_image_redaction_draws_word_level_rectangles(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "sample.png"
            Image.new("RGB", (140, 60), "white").save(image_path)
            word_index = {
                "john": [(10, 10, 40, 25)],
                "doe": [(50, 10, 75, 25)],
            }

            with patch.object(redactor, "_blur_faces", lambda img: (img, 0)), \
                 patch.object(redactor, "_redact_qr_codes", lambda img: (img, 0)), \
                 patch.object(redactor, "_redact_signatures", lambda img, index: (img, 0)), \
                 patch.object(redactor, "_build_word_index", lambda img: (word_index, [])):
                output = redactor._redact_image(
                    str(image_path),
                    [{"type": "PERSON", "text": "John Doe", "score": 1.0}],
                    mask_face=True,
                    mask_qr=True,
                )

            redacted = Image.open(io.BytesIO(output))
            self.assertEqual(redacted.getpixel((12, 12)), (0, 0, 0))
            self.assertEqual(redacted.getpixel((52, 12)), (0, 0, 0))
            self.assertEqual(redacted.getpixel((45, 12)), (255, 255, 255))


if __name__ == "__main__":
    unittest.main()
