import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from detector import analyze_text


def labels(text):
    return [(result.entity_type, text[result.start:result.end]) for result in analyze_text(text)]


class DetectorTests(unittest.TestCase):
    def test_multiple_emails_and_phone_numbers(self):
        text = (
            "Email: primary@example.com\n"
            "Secondary Email: backup@example.org\n"
            "Phone: +91 98765 43210\n"
            "Emergency Contact: 9123456789"
        )

        found = labels(text)

        self.assertIn(("EMAIL_ADDRESS", "primary@example.com"), found)
        self.assertIn(("EMAIL_ADDRESS", "backup@example.org"), found)
        self.assertIn(("PHONE_NUMBER", "+91 98765 43210"), found)
        self.assertIn(("PHONE_NUMBER", "9123456789"), found)

    def test_long_multiline_address_and_employee_id(self):
        text = (
            "Name: Rahul Sharma\n"
            "Address: Flat 12, MG Road\n"
            "Bengaluru Karnataka 560001\n"
            "Employee ID: EMP-12345"
        )

        found = labels(text)

        self.assertIn(("ADDRESS", "Flat 12, MG Road"), found)
        self.assertIn(("ADDRESS", "Bengaluru Karnataka 560001"), found)
        self.assertIn(("EMPLOYEE_ID", "EMP-12345"), found)

    def test_bank_account_does_not_override_mobile_number(self):
        text = "Phone: 9876543210\nBank Account: 50101234567890"

        found = labels(text)

        self.assertIn(("PHONE_NUMBER", "9876543210"), found)
        self.assertIn(("BANK_ACCOUNT", "50101234567890"), found)

    def test_email_wins_over_overlapping_url(self):
        text = "Visit http://help.example.com/a@test.com for details"

        found = labels(text)

        self.assertIn(("EMAIL_ADDRESS", "a@test.com"), found)
        self.assertFalse(any(entity_type == "URL" and "a@test.com" in value for entity_type, value in found))

    def test_passport_wins_over_person_overlap(self):
        text = "Passport: A1234567"

        found = labels(text)

        self.assertIn(("PASSPORT", "A1234567"), found)


if __name__ == "__main__":
    unittest.main()
