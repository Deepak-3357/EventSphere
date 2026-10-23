"""Regression checks for student event passes and OD PDF browser handling."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import create_app  # noqa: E402


class ProductionPassPdfRegressionTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config.update(TESTING=True)
        cls.event_pass_js = (ROOT / "frontend" / "assets" / "js" / "event-pass.js").read_text(encoding="utf-8")
        cls.event_pass_html = (ROOT / "frontend" / "student" / "event-pass" / "index.html").read_text(encoding="utf-8")
        cls.my_registrations_js = (ROOT / "frontend" / "assets" / "js" / "my-registrations.js").read_text(encoding="utf-8")
        cls.od_letter_js = (ROOT / "frontend" / "assets" / "js" / "od-letter.js").read_text(encoding="utf-8")

    def test_event_pass_uses_registration_contract_and_actionable_retry_errors(self):
        self.assertIn("/api/registrations/${encodeURIComponent(registrationId)}/pass", self.event_pass_js)
        self.assertIn("body.success !== true", self.event_pass_js)
        self.assertIn('status === 401', self.event_pass_js)
        self.assertIn('status === 404', self.event_pass_js)
        self.assertIn('status >= 500', self.event_pass_js)
        self.assertIn('id="retryPass"', self.event_pass_html)
        self.assertIn('registration_id=${encodeURIComponent(registration.registration_id)}', self.my_registrations_js)

    def test_event_pass_displays_registration_details_without_attendance(self):
        self.assertNotIn("qrcode@", self.event_pass_html)
        self.assertNotIn("attendanceStatus", self.event_pass_html)
        self.assertNotIn("attendanceCode", self.event_pass_html)
        self.assertNotIn("qrCode", self.event_pass_html)
        self.assertNotIn("qr_image", self.event_pass_js)
        self.assertNotIn("qr_payload", self.event_pass_js)
        self.assertNotIn("attendance_code", self.event_pass_js)
        self.assertIn("The event pass data is incomplete", self.event_pass_js)

    def test_od_download_validates_status_content_type_and_pdf_signature(self):
        self.assertIn("apiUrl(\"/api\")", self.od_letter_js)
        self.assertIn("!response.ok", self.od_letter_js)
        self.assertIn("application/pdf", self.od_letter_js)
        self.assertIn('signature !== "%PDF-"', self.od_letter_js)
        self.assertIn("safePdfFilename", self.od_letter_js)
        self.assertIn("setup(existingBody.data, session)", self.od_letter_js)
        self.assertIn("setup(body.data, session)", self.od_letter_js)


if __name__ == "__main__":
    unittest.main()
