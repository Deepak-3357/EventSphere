"""Unit coverage for the server-generated OD PDF layout."""

import io
import sys
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import create_app  # noqa: E402
from app.services.od_letter_service import generate_pdf, verify_token  # noqa: E402


class _Cursor:
    description = [type("Column", (), {"name": "status"})()]

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, *_args):
        return None

    def fetchone(self):
        return ("registered",)


class _Connection:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def cursor(self):
        return _Cursor()


def letter(**overrides):
    result = {
        "id": str(uuid.uuid4()),
        "registration_id": str(uuid.uuid4()),
        "letter_number": "OD-TEST1234",
        "issued_at": "2026-10-11T14:30:00+05:30",
        "status": "generated",
        "verification_token": "signed-token-is-not-printed-in-tests",
        "student": {"name": "A Student", "email": "student@example.test", "department": "Computing", "year": 3},
        "event": {"title": "Campus Hack Day", "event_date": "2026-10-20", "start_time": "10:00:00", "end_time": "16:00:00", "organizer": "Event Organizer"},
    }
    result.update(overrides)
    return result


class ODDocumentUnitTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config.update(TESTING=True, OD_VERIFICATION_SECRET="test-only-secret", FRONTEND_ORIGIN="https://eventsphere.example")

    def render(self, document):
        with self.app.app_context(), patch("app.services.od_letter_service.get_connection", return_value=_Connection()):
            return generate_pdf(document).read()

    def test_pdf_is_a4_and_contains_pending_generated_status(self):
        reader = PdfReader(io.BytesIO(self.render(letter())))
        self.assertEqual(len(reader.pages), 1)
        self.assertEqual(tuple(round(value, 2) for value in reader.pages[0].mediabox[2:]), (595.28, 841.89))
        text = reader.pages[0].extract_text()
        self.assertIn("ON-DUTY PERMISSION LETTER", text)
        self.assertIn("OD-TEST1234", text)
        self.assertIn("Request status: GENERATED", text)
        self.assertNotIn("APPROVED", text)

    def test_long_fields_wrap_without_creating_extra_pages(self):
        document = letter(
            student={"name": "A Very Long Student Name That Needs To Wrap Across Multiple Lines", "email": "long.student@example.test", "department": "School of Computer Science and Information Technology", "year": 4},
            event={"title": "A Very Long Campus Event Title For The Annual Interdisciplinary Innovation Showcase", "event_date": "2026-10-20", "start_time": "10:00:00", "end_time": "16:00:00", "organizer": "A Very Long Organizer Name"},
        )
        reader = PdfReader(io.BytesIO(self.render(document)))
        self.assertEqual(len(reader.pages), 1)
        text = reader.pages[0].extract_text()
        self.assertIn("Very Long Student Name", text)
        self.assertIn("Annual Interdisciplinary Innovation Showcase", text)

    def test_missing_optional_fields_use_safe_fallbacks(self):
        document = letter(student={"name": "Student", "email": None, "department": None, "year": None}, event={"title": "Event", "event_date": "2026-10-20", "start_time": None, "end_time": None, "organizer": None})
        reader = PdfReader(io.BytesIO(self.render(document)))
        self.assertEqual(len(reader.pages), 1)
        self.assertIn("Not available", reader.pages[0].extract_text())

    def test_malformed_verification_tokens_are_rejected_without_server_errors(self):
        with self.app.app_context():
            self.assertFalse(verify_token("not-base64", str(uuid.uuid4())))
            self.assertFalse(verify_token("eyJub3QiOiJqc29uIn0", str(uuid.uuid4())))


if __name__ == "__main__":
    unittest.main()
