"""Phase 2 attendance-code contract and security regression tests."""

import re
import sys
import unittest
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import create_app  # noqa: E402
from app.db import get_connection  # noqa: E402
from app.services.attendance_service import _code_hash, _code_fernet, _new_attendance_code  # noqa: E402
from app.services.attendance_service import ensure_attendance_code  # noqa: E402
from integration_support import require_integration_database  # noqa: E402


class AttendanceCodeContractTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config.update(
            TESTING=True,
            ATTENDANCE_QR_SECRET="test-only-qr-secret",
            ATTENDANCE_CODE_SECRET="test-only-code-secret",
            ATTENDANCE_CODE_ENCRYPTION_KEY="uvxXcu2SeDUH0q4hXDJA-G23B_dW3j4WKjJdKkJg1Gk=",
        )

    def test_codes_are_exactly_six_digits(self):
        with self.app.app_context():
            self.assertTrue(all(re.fullmatch(r"\d{6}", _new_attendance_code()) for _ in range(100)))

    def test_hash_is_event_scoped_and_ciphertext_round_trips(self):
        event_one, event_two = str(uuid.uuid4()), str(uuid.uuid4())
        with self.app.app_context():
            digest = _code_hash(event_one, "004281")
            self.assertNotEqual(digest, _code_hash(event_two, "004281"))
            encrypted = _code_fernet().encrypt(b"004281")
            self.assertEqual(_code_fernet().decrypt(encrypted), b"004281")

    def test_backend_and_frontend_contracts_are_present(self):
        route = (ROOT / "backend/app/routes/attendance.py").read_text(encoding="utf-8")
        service = (ROOT / "backend/app/services/attendance_service.py").read_text(encoding="utf-8")
        migration = (ROOT / "supabase/migrations/20261011100000_attendance_codes.sql").read_text(encoding="utf-8")
        page = (ROOT / "frontend" / "assets" / "js" / "attendance-scanner.js").read_text(encoding="utf-8")
        attendance_html = (ROOT / "frontend" / "organizer" / "attendance" / "index.html").read_text(encoding="utf-8")
        self.assertIn("/attendance/manual-check-in", route)
        self.assertIn("_record_attendance", service)
        self.assertIn("attendance_codes_event_hash_unique", migration)
        self.assertIn("manual-check-in", page)
        self.assertIn("finally", page)
        self.assertIn('id="manualCodeForm"', attendance_html)


class AttendanceCodeIntegrationTestCase(unittest.TestCase):
    """Database-backed cases run only against the explicitly approved test DB."""

    @classmethod
    def setUpClass(cls):
        require_integration_database()
        cls.app = create_app()
        cls.app.config.update(
            TESTING=True,
            ATTENDANCE_QR_SECRET="integration-qr-secret",
            ATTENDANCE_CODE_SECRET="integration-code-secret",
            ATTENDANCE_CODE_ENCRYPTION_KEY="uvxXcu2SeDUH0q4hXDJA-G23B_dW3j4WKjJdKkJg1Gk=",
        )
        cls.client = cls.app.test_client()
        cls.organizer = "00000000-0000-0000-0000-000000000003"
        cls.student = "00000000-0000-0000-0000-000000000001"

    def setUp(self):
        self.event_id, self.registration_id = str(uuid.uuid4()), str(uuid.uuid4())
        now = datetime.now()
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """insert into events (id,title,description,category_id,organizer_id,venue_id,event_date,start_time,end_time,capacity,registration_deadline,status)
                       values(%s,'Code Test','Code test',%s,%s,%s,%s,%s,%s,10,now(),'published')""",
                    (self.event_id, "10000000-0000-0000-0000-000000000001", self.organizer, "20000000-0000-0000-0000-000000000004", now.date(), (now - timedelta(minutes=10)).time().replace(second=0, microsecond=0), (now + timedelta(hours=1)).time().replace(second=0, microsecond=0)),
                )
                cursor.execute("insert into registrations(id,event_id,student_id,status) values(%s,%s,%s,'registered')", (self.registration_id, self.event_id, self.student))
                self.code = ensure_attendance_code(cursor, self.registration_id, self.event_id)

    def tearDown(self):
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("delete from attendance_code_attempts where event_id=%s", (self.event_id,))
                cursor.execute("delete from attendance_codes where event_id=%s", (self.event_id,))
                cursor.execute("delete from attendance where event_id=%s", (self.event_id,))
                cursor.execute("delete from registrations where event_id=%s", (self.event_id,))
                cursor.execute("delete from events where id=%s", (self.event_id,))

    def _headers(self):
        return {"Authorization": "Bearer integration-token"}

    def test_valid_code_persists_attendance_and_duplicate_is_rejected(self):
        user = {"id": self.organizer}
        profile = {"id": self.organizer, "role": "organizer"}
        with patch.multiple("app.routes.auth", verify_access_token=lambda token: user, _load_profile=lambda user_id: profile):
            response = self.client.post("/api/attendance/manual-check-in", json={"event_id": self.event_id, "code": self.code}, headers=self._headers())
            duplicate = self.client.post("/api/attendance/manual-check-in", json={"event_id": self.event_id, "code": self.code}, headers=self._headers())
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()["data"]["status"], "present")
        self.assertEqual(duplicate.status_code, 409)

    def test_wrong_event_code_and_student_access_are_rejected(self):
        other_event = str(uuid.uuid4())
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("insert into events (id,title,description,category_id,organizer_id,venue_id,event_date,start_time,end_time,capacity,registration_deadline,status) values(%s,'Other','Other',%s,%s,%s,current_date,localtime,localtime + interval '1 hour',10,now(),'published')", (other_event, "10000000-0000-0000-0000-000000000001", self.organizer, "20000000-0000-0000-0000-000000000004"))
        try:
            with patch.multiple("app.routes.auth", verify_access_token=lambda token: {"id": self.organizer}, _load_profile=lambda user_id: {"id": self.organizer, "role": "organizer"}):
                response = self.client.post("/api/attendance/manual-check-in", json={"event_id": other_event, "code": self.code}, headers=self._headers())
            self.assertEqual(response.status_code, 400)
            with patch.multiple("app.routes.auth", verify_access_token=lambda token: {"id": self.student}, _load_profile=lambda user_id: {"id": self.student, "role": "student"}):
                student_response = self.client.post("/api/attendance/manual-check-in", json={"event_id": self.event_id, "code": self.code}, headers=self._headers())
            self.assertEqual(student_response.status_code, 403)
        finally:
            with get_connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute("delete from events where id=%s", (other_event,))


if __name__ == "__main__":
    unittest.main()
