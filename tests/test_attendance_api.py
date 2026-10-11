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
from integration_support import require_integration_database, resolve_profile_id  # noqa: E402


STUDENT_ONE = {"id": "00000000-0000-0000-0000-000000000001", "email": "student1@example.test"}
STUDENT_TWO = {"id": "00000000-0000-0000-0000-000000000002", "email": "student2@example.test"}
ORGANIZER = {"id": resolve_profile_id("rohan.organizer@example.test", "00000000-0000-0000-0000-000000000003"), "email": "organizer@example.test"}
OTHER_ORGANIZER = {"id": "00000000-0000-0000-0000-000000000004", "email": "other@example.test"}
ADMIN = {"id": resolve_profile_id("admin@example.test", "00000000-0000-0000-0000-000000000005"), "email": "admin@example.test"}


def profile(user, role):
    return {"id": user["id"], "full_name": role.title(), "email": user["email"], "role": role}


class AttendanceApiTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        require_integration_database()
        app = create_app()
        app.config.update(TESTING=True)
        cls.client = app.test_client()

    def setUp(self):
        self.event_id = str(uuid.uuid4())
        self.registration_id = str(uuid.uuid4())
        now = datetime.now()
        self.event_date = now.date()
        self.start = (now - timedelta(minutes=10)).time().replace(second=0, microsecond=0)
        self.end = (now + timedelta(hours=1)).time().replace(second=0, microsecond=0)
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """insert into events (id, title, description, category_id, organizer_id, venue_id,
                       event_date, start_time, end_time, capacity, registration_deadline, status)
                       values (%s, %s, 'Attendance test', %s, %s, %s, %s, %s, %s, 10, now(), 'published')""",
                    (self.event_id, "Attendance Test", "10000000-0000-0000-0000-000000000001", ORGANIZER["id"],
                     "20000000-0000-0000-0000-000000000004", self.event_date, self.start, self.end),
                )
                cursor.execute(
                    "insert into registrations (id, event_id, student_id, status) values (%s, %s, %s, 'registered')",
                    (self.registration_id, self.event_id, STUDENT_ONE["id"]),
                )

    def tearDown(self):
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("delete from attendance where event_id = %s", (self.event_id,))
                cursor.execute("delete from registrations where event_id = %s", (self.event_id,))
                cursor.execute("delete from events where id = %s", (self.event_id,))

    def _auth(self, user, role):
        return patch.multiple("app.routes.auth", verify_access_token=lambda token: user,
                              _load_profile=lambda user_id: profile(user, role))

    def _headers(self, token="token"):
        return {"Authorization": f"Bearer {token}"}

    def _pass_payload(self):
        with self._auth(STUDENT_ONE, "student"):
            response = self.client.get(f"/api/registrations/{self.registration_id}/pass", headers=self._headers())
        self.assertEqual(response.status_code, 200)
        return response.get_json()["data"]["qr_payload"]

    def test_pass_requires_auth_and_owner(self):
        self.assertEqual(self.client.get(f"/api/registrations/{self.registration_id}/pass").status_code, 401)
        with self._auth(STUDENT_TWO, "student"):
            response = self.client.get(f"/api/registrations/{self.registration_id}/pass", headers=self._headers())
        self.assertEqual(response.status_code, 404)

    def test_pass_returns_safe_payload_and_attendance_state(self):
        payload = self._pass_payload()
        self.assertIn("eventsphere_attendance", payload)
        self.assertNotIn("password", payload.lower())

    def test_malformed_and_tampered_qr_are_rejected(self):
        with self._auth(ORGANIZER, "organizer"):
            malformed = self.client.post("/api/attendance/check-in", json={"qr_payload": "not-json"}, headers=self._headers())
            tampered = self.client.post("/api/attendance/check-in", json={"qr_payload": self._pass_payload().replace("eventsphere_attendance", "other_type")}, headers=self._headers())
        self.assertEqual(malformed.status_code, 400)
        self.assertEqual(tampered.status_code, 400)

    def test_role_and_ownership_are_enforced(self):
        payload = self._pass_payload()
        with self._auth(STUDENT_ONE, "student"):
            self.assertEqual(self.client.post("/api/attendance/check-in", json={"qr_payload": payload}, headers=self._headers()).status_code, 403)
        with self._auth(OTHER_ORGANIZER, "organizer"):
            self.assertEqual(self.client.post("/api/attendance/check-in", json={"qr_payload": payload}, headers=self._headers()).status_code, 403)

    def test_check_in_and_duplicate_protection(self):
        payload = self._pass_payload()
        with self._auth(ORGANIZER, "organizer"):
            first = self.client.post("/api/attendance/check-in", json={"qr_payload": payload}, headers=self._headers())
            duplicate = self.client.post("/api/attendance/check-in", json={"qr_payload": payload}, headers=self._headers())
        self.assertEqual(first.status_code, 201)
        self.assertEqual(duplicate.status_code, 409)

    def test_admin_can_list_stats_and_student_cannot(self):
        payload = self._pass_payload()
        with self._auth(ORGANIZER, "organizer"):
            self.client.post("/api/attendance/check-in", json={"qr_payload": payload}, headers=self._headers())
        with self._auth(ADMIN, "admin"):
            response = self.client.get(f"/api/events/{self.event_id}/attendance", headers=self._headers())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["data"]["summary"]["checked_in"], 1)
        with self._auth(STUDENT_ONE, "student"):
            self.assertEqual(self.client.get(f"/api/events/{self.event_id}/attendance", headers=self._headers()).status_code, 403)

    def test_other_organizer_cannot_list_report(self):
        with self._auth(OTHER_ORGANIZER, "organizer"):
            response = self.client.get(f"/api/events/{self.event_id}/attendance", headers=self._headers())
        self.assertEqual(response.status_code, 403)

    def test_attendance_table_has_unique_registration_constraint(self):
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("select indexname from pg_indexes where tablename = 'attendance'")
                indexes = {row[0] for row in cursor.fetchall()}
        self.assertTrue(any("registration" in name for name in indexes))


if __name__ == "__main__":
    unittest.main()
