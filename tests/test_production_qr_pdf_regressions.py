"""Regression checks for production QR passes and OD PDF browser handling."""

import base64
import io
import json
import sys
import unittest
import uuid
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import create_app  # noqa: E402
from app.services.attendance_service import _qr_image_data_url, _signed_payload, _verify_payload, _window_is_open  # noqa: E402


class ProductionQrPdfRegressionTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config.update(TESTING=True, ATTENDANCE_QR_SECRET="regression-secret")
        cls.event_pass_js = (ROOT / "frontend" / "assets" / "js" / "event-pass.js").read_text(encoding="utf-8")
        cls.event_pass_html = (ROOT / "frontend" / "student" / "event-pass" / "index.html").read_text(encoding="utf-8")
        cls.od_letter_js = (ROOT / "frontend" / "assets" / "js" / "od-letter.js").read_text(encoding="utf-8")
        cls.attendance_scanner_js = (ROOT / "frontend" / "assets" / "js" / "attendance-scanner.js").read_text(encoding="utf-8")

    def test_signed_payload_generates_a_valid_png_for_the_scanner(self):
        registration_id = str(uuid.uuid4())
        with self.app.app_context():
            payload = _signed_payload(registration_id)
            image_url = _qr_image_data_url(payload)
            verified_registration_id = _verify_payload(payload)
        image_bytes = base64.b64decode(image_url.removeprefix("data:image/png;base64,"))
        with Image.open(io.BytesIO(image_bytes)) as image:
            self.assertEqual(image.format, "PNG")
            self.assertGreater(image.width, 0)
        self.assertEqual(verified_registration_id, registration_id)
        self.assertEqual(json.loads(payload)["type"], "eventsphere_attendance")

    def test_attendance_window_uses_configured_campus_timezone_and_boundaries(self):
        from datetime import datetime, timedelta
        from zoneinfo import ZoneInfo

        timezone = ZoneInfo("Asia/Kolkata")
        event_date = datetime(2026, 10, 11, tzinfo=timezone).date()
        start_time = datetime(2026, 10, 11, 10, 0, tzinfo=timezone).time()
        end_time = datetime(2026, 10, 11, 11, 0, tzinfo=timezone).time()
        window_start = datetime(2026, 10, 11, 9, 30, tzinfo=timezone)
        window_end = datetime(2026, 10, 11, 13, 0, tzinfo=timezone)
        with self.app.app_context():
            self.app.config.update(ATTENDANCE_TIMEZONE="Asia/Kolkata", ATTENDANCE_EARLY_MINUTES=30, ATTENDANCE_LATE_MINUTES=120)
            self.assertFalse(_window_is_open(event_date, start_time, end_time, now=window_start - timedelta(seconds=1)))
            self.assertTrue(_window_is_open(event_date, start_time, end_time, now=window_start))
            self.assertTrue(_window_is_open(event_date, start_time, end_time, now=window_start + timedelta(hours=1)))
            self.assertTrue(_window_is_open(event_date, start_time, end_time, now=window_end))
            self.assertFalse(_window_is_open(event_date, start_time, end_time, now=window_end + timedelta(seconds=1)))

    def test_event_pass_uses_backend_qr_image_and_handles_failures(self):
        self.assertNotIn("qrcode@", self.event_pass_html)
        self.assertIn('pass.qr_image.startsWith("data:image/png;base64,")', self.event_pass_js)
        self.assertIn("The event pass data is incomplete", self.event_pass_js)
        self.assertIn("does not contain a valid signed QR payload", self.event_pass_js)
        self.assertIn("qrCode.onerror", self.event_pass_js)

    def test_qr_payload_contract_is_signed_json_and_submitted_unchanged(self):
        registration_id = str(uuid.uuid4())
        with self.app.app_context():
            payload = _signed_payload(registration_id)
            document = json.loads(payload)
        self.assertEqual(set(document), {"registration_id", "token", "type"})
        self.assertEqual(document["registration_id"], registration_id)
        self.assertEqual(document["type"], "eventsphere_attendance")
        self.assertIn('JSON.stringify({ qr_payload: qrPayload })', self.attendance_scanner_js)
        self.assertNotIn('JSON.stringify({ qr_payload: JSON.stringify', self.attendance_scanner_js)
        self.assertIn("normalizeDecodedPayload(decodedText)", self.attendance_scanner_js)
        self.assertIn('typeof document === "string"', self.attendance_scanner_js)
        self.assertIn("not a valid EventSphere attendance pass", self.attendance_scanner_js)

    def test_od_download_validates_status_content_type_and_pdf_signature(self):
        self.assertIn("apiUrl(\"/api\")", self.od_letter_js)
        self.assertIn("!response.ok", self.od_letter_js)
        self.assertIn("application/pdf", self.od_letter_js)
        self.assertIn('signature !== "%PDF-"', self.od_letter_js)
        self.assertIn("safePdfFilename", self.od_letter_js)
        self.assertIn("setup(existingBody.data, session)", self.od_letter_js)
        self.assertIn("setup(body.data, session)", self.od_letter_js)

    def test_scanner_requires_confirmed_backend_attendance(self):
        self.assertIn("QR detected. Verifying attendance", self.attendance_scanner_js)
        self.assertIn("result.success !== true", self.attendance_scanner_js)
        self.assertIn("!attendance?.attendance_id", self.attendance_scanner_js)
        self.assertIn('attendance.status !== "present"', self.attendance_scanner_js)
        self.assertIn("checkInInProgress", self.attendance_scanner_js)
        self.assertIn("Check-in recorded, but the attendance list could not be refreshed", self.attendance_scanner_js)
        self.assertIn("fetchWithTimeout", self.attendance_scanner_js)
        self.assertIn('error.name === "AbortError"', self.attendance_scanner_js)
        self.assertIn("finally", self.attendance_scanner_js)


if __name__ == "__main__":
    unittest.main()
