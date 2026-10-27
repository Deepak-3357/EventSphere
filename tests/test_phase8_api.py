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
from app.db import get_connection  # noqa: E402
from integration_support import require_integration_database, resolve_profile_id  # noqa: E402

STUDENT_ONE = {"id": "00000000-0000-0000-0000-000000000001", "email": "student1@example.test"}
STUDENT_TWO = {"id": "00000000-0000-0000-0000-000000000002", "email": "student2@example.test"}
ORGANIZER = {"id": resolve_profile_id("rohan.organizer@example.test", "00000000-0000-0000-0000-000000000003"), "email": "organizer@example.test"}
OTHER = {"id": "00000000-0000-0000-0000-000000000004", "email": "other@example.test"}
ADMIN = {"id": resolve_profile_id("admin@example.test", "00000000-0000-0000-0000-000000000005"), "email": "admin@example.test"}


def profile(user, role):
    return {"id": user["id"], "full_name": role.title(), "email": user["email"], "role": role}


class Phase8ApiTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        require_integration_database()
        app = create_app(); app.config.update(TESTING=True); cls.client = app.test_client()

    def setUp(self):
        self.event_id, self.registration_id = str(uuid.uuid4()), str(uuid.uuid4())
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""insert into events (id, title, description, category_id, organizer_id,
                    event_date, start_time, end_time, capacity, registration_deadline, status)
                    values (%s, 'Phase 8 OD Event', 'Test', %s, %s, %s, '2099-11-20', '10:00', '12:00', 20,
                    '2099-11-19 10:00:00+05:30', 'published')""", (self.event_id, "10000000-0000-0000-0000-000000000001", ORGANIZER["id"]))
                cursor.execute("insert into registrations (id, event_id, student_id) values (%s, %s, %s)", (self.registration_id, self.event_id, STUDENT_ONE["id"]))

    def tearDown(self):
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("delete from od_letters where event_id = %s", (self.event_id,))
                cursor.execute("delete from registrations where event_id = %s", (self.event_id,))
                cursor.execute("delete from events where id = %s", (self.event_id,))

    def auth(self, user, role):
        return patch.multiple("app.routes.auth", verify_access_token=lambda token: user, _load_profile=lambda user_id: profile(user, role))

    def headers(self): return {"Authorization": "Bearer phase8-token"}

    def test_student_dashboard_requires_authentication(self):
        self.assertEqual(self.client.get("/api/dashboard/student").status_code, 401)

    def test_student_dashboard_is_student_scoped(self):
        with self.auth(STUDENT_ONE, "student"):
            response = self.client.get("/api/dashboard/student", headers=self.headers())
        self.assertEqual(response.status_code, 200)
        self.assertTrue(all(item["registration_id"] != "other-student-registration" for item in response.get_json()["data"]["upcoming_events"]))

    def test_organizer_dashboard_requires_organizer_role(self):
        with self.auth(STUDENT_ONE, "student"):
            self.assertEqual(self.client.get("/api/dashboard/organizer", headers=self.headers()).status_code, 403)

    def test_organizer_dashboard_is_owned_event_scoped(self):
        other_event_id = str(uuid.uuid4())
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""insert into events (id, title, description, category_id, organizer_id,
                    event_date, start_time, end_time, capacity, registration_deadline, status)
                    values (%s, 'Other organizer event', 'Test', %s, %s, %s, '2099-11-21', '10:00', '12:00', 20,
                    '2099-11-20 10:00:00+05:30', 'published')""", (other_event_id, "10000000-0000-0000-0000-000000000001", OTHER["id"]))
        with self.auth(ORGANIZER, "organizer"):
            response = self.client.get("/api/dashboard/organizer", headers=self.headers())
        data = response.get_json()["data"]
        with get_connection() as connection:
            with connection.cursor() as cursor: cursor.execute("delete from events where id = %s", (other_event_id,))
        self.assertEqual(response.status_code, 200); self.assertIn(self.event_id, [item["id"] for item in data["events"]]); self.assertNotIn(other_event_id, [item["id"] for item in data["events"]])
        self.assertIn("total_events", data["stats"])

    def test_admin_dashboard_is_platform_scoped(self):
        with self.auth(ADMIN, "admin"):
            response = self.client.get("/api/dashboard/admin", headers=self.headers())
        self.assertEqual(response.status_code, 200); self.assertGreaterEqual(response.get_json()["data"]["stats"]["total_events"], 1)

    def test_od_requires_auth_and_owner(self):
        self.assertEqual(self.client.post(f"/api/registrations/{self.registration_id}/od-letter").status_code, 401)
        with self.auth(STUDENT_TWO, "student"):
            response = self.client.post(f"/api/registrations/{self.registration_id}/od-letter", headers=self.headers())
        self.assertEqual(response.status_code, 404)

    def test_od_generation_is_reused_and_pdf_is_valid(self):
        with self.auth(STUDENT_ONE, "student"):
            first = self.client.post(f"/api/registrations/{self.registration_id}/od-letter", headers=self.headers())
            second = self.client.get(f"/api/registrations/{self.registration_id}/od-letter", headers=self.headers())
        self.assertEqual(first.status_code, 201); self.assertEqual(second.status_code, 200)
        first_data, second_data = first.get_json()["data"], second.get_json()["data"]
        self.assertEqual(first_data["id"], second_data["id"]); self.assertTrue(first_data["letter_number"].startswith("OD-"))
        with self.auth(STUDENT_ONE, "student"):
            download = self.client.get(f"/api/od-letters/{first_data['id']}/download", headers=self.headers())
        self.assertEqual(download.status_code, 200); self.assertEqual(download.mimetype, "application/pdf"); self.assertTrue(download.data.startswith(b"%PDF")); self.assertIn("attachment", download.headers.get("Content-Disposition", "")); self.assertIn(first_data["letter_number"], download.headers.get("Content-Disposition", ""))
        reader = PdfReader(io.BytesIO(download.data)); self.assertEqual(len(reader.pages), 1); self.assertIn("ON-DUTY LETTER", reader.pages[0].extract_text())

    def test_od_download_rejects_missing_and_non_owner_requests(self):
        with self.auth(STUDENT_ONE, "student"):
            generated = self.client.post(f"/api/registrations/{self.registration_id}/od-letter", headers=self.headers()).get_json()["data"]
        with self.auth(STUDENT_TWO, "student"):
            unauthorized = self.client.get(f"/api/od-letters/{generated['id']}/download", headers=self.headers())
        with self.auth(STUDENT_ONE, "student"):
            missing = self.client.get(f"/api/od-letters/{uuid.uuid4()}/download", headers=self.headers())
        self.assertEqual(unauthorized.status_code, 404)
        self.assertEqual(missing.status_code, 404)

    def test_od_verification_accepts_signed_token_and_rejects_invalid(self):
        with self.auth(STUDENT_ONE, "student"):
            generated = self.client.post(f"/api/registrations/{self.registration_id}/od-letter", headers=self.headers()).get_json()["data"]
        valid = self.client.get(f"/api/od-letters/{generated['id']}/verify?token={generated['verification_token']}")
        invalid = self.client.get(f"/api/od-letters/{generated['id']}/verify?token=bad")
        self.assertEqual(valid.status_code, 200); self.assertTrue(valid.get_json()["data"]["valid"]); self.assertEqual(invalid.status_code, 404)

    def test_cancelled_registration_cannot_download_existing_od(self):
        with self.auth(STUDENT_ONE, "student"):
            generated = self.client.post(f"/api/registrations/{self.registration_id}/od-letter", headers=self.headers()).get_json()["data"]
        with get_connection() as connection:
            with connection.cursor() as cursor: cursor.execute("update registrations set status = 'cancelled' where id = %s", (self.registration_id,))
        with self.auth(STUDENT_ONE, "student"):
            response = self.client.get(f"/api/od-letters/{generated['id']}/download", headers=self.headers())
        self.assertEqual(response.status_code, 409)


if __name__ == "__main__": unittest.main()
