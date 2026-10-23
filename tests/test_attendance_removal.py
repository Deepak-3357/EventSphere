"""Regression tests verifying complete removal of the attendance module."""

import sys
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import create_app  # noqa: E402

STUDENT = {"id": "00000000-0000-0000-0000-000000000001", "email": "student@example.test"}
ORGANIZER = {"id": "00000000-0000-0000-0000-000000000003", "email": "organizer@example.test"}


class AttendanceRemovalTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config.update(TESTING=True)
        self.client = self.app.test_client()

    def _auth(self, user=STUDENT, role="student"):
        return patch.multiple(
            "app.routes.auth",
            verify_access_token=lambda token: user,
            _load_profile=lambda user_id: {"id": user["id"], "full_name": role.title(), "role": role},
        )

    def test_attendance_blueprint_is_not_registered(self):
        self.assertNotIn("attendance", self.app.blueprints)

    def test_attendance_api_endpoints_return_404(self):
        event_id = str(uuid.uuid4())
        with self._auth(ORGANIZER, "organizer"):
            headers = {"Authorization": "Bearer test-token"}
            res1 = self.client.post("/api/attendance/check-in", json={"qr_payload": "test"}, headers=headers)
            self.assertEqual(res1.status_code, 404)

            res2 = self.client.post("/api/attendance/manual-check-in", json={"event_id": event_id, "code": "123456"}, headers=headers)
            self.assertEqual(res2.status_code, 404)

            res3 = self.client.get(f"/api/events/{event_id}/attendance", headers=headers)
            self.assertEqual(res3.status_code, 404)

    def test_event_pass_endpoint_is_under_registrations_bp(self):
        reg_id = str(uuid.uuid4())
        mock_pass = {
            "registration_id": reg_id,
            "event_id": str(uuid.uuid4()),
            "event_title": "Clean Pass Event",
            "student_name": "Student Name",
            "registration_status": "registered",
        }
        with self._auth(STUDENT, "student"), patch(
            "app.services.registration_service.get_event_pass", return_value=mock_pass
        ):
            res = self.client.get(
                f"/api/registrations/{reg_id}/pass",
                headers={"Authorization": "Bearer test-token"},
            )
            self.assertEqual(res.status_code, 200)
            data = res.get_json()["data"]
            self.assertEqual(data["registration_id"], reg_id)
            self.assertNotIn("attendance", data)
            self.assertNotIn("attendance_code", data)
            self.assertNotIn("qr_payload", data)
            self.assertNotIn("qr_image", data)

    def test_attendance_frontend_files_are_deleted(self):
        scanner_js = ROOT / "frontend" / "assets" / "js" / "attendance-scanner.js"
        organizer_attendance_dir = ROOT / "frontend" / "organizer" / "attendance"
        admin_attendance_dir = ROOT / "frontend" / "admin" / "attendance"

        self.assertFalse(scanner_js.exists(), "attendance-scanner.js must be removed")
        self.assertFalse(organizer_attendance_dir.exists(), "organizer attendance directory must be removed")
        self.assertFalse(admin_attendance_dir.exists(), "admin attendance directory must be removed")


if __name__ == "__main__":
    unittest.main()
