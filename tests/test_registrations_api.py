import sys
import unittest
import uuid
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
    return {"id": user["id"], "full_name": role.title(), "role": role}


class RegistrationApiTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        require_integration_database()
        app = create_app()
        app.config.update(TESTING=True)
        cls.client = app.test_client()

    def setUp(self):
        self.event_id = str(uuid.uuid4())
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """insert into events
                       (id, title, description, category_id, organizer_id, venue_id,
                        event_date, start_time, end_time, capacity, registration_deadline, status)
                       values (%s, %s, %s, %s, %s, %s, '2099-12-10', '10:00', '12:00', 1,
                               '2099-12-09 18:00:00+05:30', 'published')""",
                    (
                        self.event_id,
                        f"Registration Test {self.event_id}",
                        "Registration workflow test event",
                        "10000000-0000-0000-0000-000000000001",
                        ORGANIZER["id"],
                        "20000000-0000-0000-0000-000000000004",
                    ),
                )

    def tearDown(self):
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("delete from registrations where event_id = %s", (self.event_id,))
                cursor.execute("delete from events where id = %s", (self.event_id,))

    def _auth(self, user, role):
        return patch.multiple(
            "app.routes.auth",
            verify_access_token=lambda token: user,
            _load_profile=lambda user_id: profile(user, role),
        )

    def test_register_duplicate_capacity_cancel_and_reregister(self):
        with self._auth(STUDENT_ONE, "student"):
            first = self.client.post(
                f"/api/events/{self.event_id}/register",
                headers={"Authorization": "Bearer student-one-token"},
            )
            duplicate = self.client.post(
                f"/api/events/{self.event_id}/register",
                headers={"Authorization": "Bearer student-one-token"},
            )
        self.assertEqual(first.status_code, 201)
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(duplicate.get_json()["error"]["code"], "ALREADY_REGISTERED")

        with self._auth(STUDENT_TWO, "student"):
            full = self.client.post(
                f"/api/events/{self.event_id}/register",
                headers={"Authorization": "Bearer student-two-token"},
            )
        self.assertEqual(full.status_code, 409)
        self.assertEqual(full.get_json()["error"]["code"], "EVENT_FULL")

        with self._auth(STUDENT_ONE, "student"):
            cancelled = self.client.delete(
                f"/api/events/{self.event_id}/register",
                headers={"Authorization": "Bearer student-one-token"},
            )
        self.assertEqual(cancelled.status_code, 200)
        self.assertEqual(cancelled.get_json()["data"]["status"], "cancelled")

        with self._auth(STUDENT_TWO, "student"):
            second = self.client.post(
                f"/api/events/{self.event_id}/register",
                headers={"Authorization": "Bearer student-two-token"},
            )
        self.assertEqual(second.status_code, 201)

    def test_my_registrations_and_event_detail_counts(self):
        with self._auth(STUDENT_ONE, "student"):
            created = self.client.post(
                f"/api/events/{self.event_id}/register",
                headers={"Authorization": "Bearer student-one-token"},
            )
            mine = self.client.get(
                "/api/my-registrations?status=registered",
                headers={"Authorization": "Bearer student-one-token"},
            )
            with patch("app.routes.events.verify_access_token", return_value=STUDENT_ONE), patch(
                "app.routes.events._load_profile", return_value=profile(STUDENT_ONE, "student")
            ):
                detail = self.client.get(
                    f"/api/events/{self.event_id}",
                    headers={"Authorization": "Bearer student-one-token"},
                )
        self.assertEqual(created.status_code, 201)
        self.assertEqual(mine.status_code, 200)
        self.assertTrue(any(item["event"]["id"] == self.event_id for item in mine.get_json()["data"]))
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.get_json()["data"]["registered_count"], 1)
        self.assertEqual(detail.get_json()["data"]["available_seats"], 0)
        self.assertTrue(detail.get_json()["data"]["is_registered"])

    def test_organizer_and_admin_participant_views_are_scoped(self):
        with self._auth(STUDENT_ONE, "student"):
            created = self.client.post(
                f"/api/events/{self.event_id}/register",
                headers={"Authorization": "Bearer student-one-token"},
            )
        registration_id = created.get_json()["data"]["registration_id"]

        with self._auth(ORGANIZER, "organizer"):
            own = self.client.get(
                f"/api/events/{self.event_id}/registrations",
                headers={"Authorization": "Bearer organizer-token"},
            )
        self.assertEqual(own.status_code, 200)
        self.assertEqual(len(own.get_json()["data"]), 1)

        with self._auth(OTHER_ORGANIZER, "organizer"):
            other = self.client.get(
                f"/api/events/{self.event_id}/registrations",
                headers={"Authorization": "Bearer other-organizer-token"},
            )
        self.assertEqual(other.status_code, 403)

        with self._auth(ADMIN, "admin"):
            admin = self.client.get(
                f"/api/registrations?event_id={self.event_id}",
                headers={"Authorization": "Bearer admin-token"},
            )
        self.assertEqual(admin.status_code, 200)
        self.assertTrue(any(item["registration_id"] == registration_id for item in admin.get_json()["data"]))

    def test_student_cannot_access_another_registration_and_unauthenticated_is_rejected(self):
        with self._auth(STUDENT_ONE, "student"):
            created = self.client.post(
                f"/api/events/{self.event_id}/register",
                headers={"Authorization": "Bearer student-one-token"},
            )
        registration_id = created.get_json()["data"]["registration_id"]

        with self._auth(STUDENT_TWO, "student"):
            other = self.client.get(
                f"/api/registrations/{registration_id}",
                headers={"Authorization": "Bearer student-two-token"},
            )
        self.assertEqual(other.status_code, 404)
        self.assertEqual(self.client.post(f"/api/events/{self.event_id}/register").status_code, 401)

    def test_closed_event_rejects_registration(self):
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("update events set registration_deadline = now() - interval '1 hour' where id = %s", (self.event_id,))
        with self._auth(STUDENT_ONE, "student"):
            response = self.client.post(
                f"/api/events/{self.event_id}/register",
                headers={"Authorization": "Bearer student-one-token"},
            )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["error"]["code"], "REGISTRATION_CLOSED")


if __name__ == "__main__":
    unittest.main()
