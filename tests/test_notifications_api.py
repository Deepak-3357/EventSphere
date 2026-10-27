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


def profile(user, role):
    return {"id": user["id"], "full_name": role.title(), "role": role}


class NotificationApiTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        require_integration_database()
        app = create_app()
        app.config.update(TESTING=True)
        cls.client = app.test_client()

    def setUp(self):
        self.event_id = str(uuid.uuid4())
        self.event_title = f"Notification Test {self.event_id}"
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """insert into events
                       (id, title, description, category_id, organizer_id,
                        event_date, start_time, end_time, capacity, registration_deadline, status)
                       values (%s, %s, %s, %s, %s, %s, '2099-12-20', '10:00', '12:00', 10,
                               '2099-12-19 18:00:00+05:30', 'published')""",
                    (
                        self.event_id,
                        self.event_title,
                        "Notification workflow test event",
                        "10000000-0000-0000-0000-000000000001",
                        ORGANIZER["id"],
                    ),
                )

    def tearDown(self):
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("delete from registrations where event_id = %s", (self.event_id,))
                cursor.execute("delete from events where id = %s", (self.event_id,))
                cursor.execute("delete from notifications where message like %s", (f"%{self.event_title}%",))

    def _auth(self, user, role):
        return patch.multiple(
            "app.routes.auth",
            verify_access_token=lambda token: user,
            _load_profile=lambda user_id: profile(user, role),
        )

    def _register(self, user, token):
        with self._auth(user, "student"):
            return self.client.post(
                f"/api/events/{self.event_id}/register",
                headers={"Authorization": f"Bearer {token}"},
            )

    def test_registration_and_cancellation_generate_notifications(self):
        registered = self._register(STUDENT_ONE, "student-one-token")
        self.assertEqual(registered.status_code, 201)

        with self._auth(STUDENT_ONE, "student"):
            confirmation = self.client.get("/api/notifications?type=registration&limit=100", headers={"Authorization": "Bearer student-one-token"})
        confirmation_items = confirmation.get_json()["data"]
        self.assertTrue(any(self.event_title in item["message"] for item in confirmation_items))

        with self._auth(STUDENT_ONE, "student"):
            cancelled = self.client.delete(f"/api/events/{self.event_id}/register", headers={"Authorization": "Bearer student-one-token"})
        self.assertEqual(cancelled.status_code, 200)

        with self._auth(STUDENT_ONE, "student"):
            cancellation = self.client.get("/api/notifications?type=cancellation&limit=100", headers={"Authorization": "Bearer student-one-token"})
        self.assertTrue(any(self.event_title in item["message"] for item in cancellation.get_json()["data"]))

    def test_failed_duplicate_does_not_create_extra_confirmation(self):
        self.assertEqual(self._register(STUDENT_ONE, "student-one-token").status_code, 201)
        with self._auth(STUDENT_ONE, "student"):
            before = self.client.get("/api/notifications?type=registration&limit=100", headers={"Authorization": "Bearer student-one-token"}).get_json()["data"]
            duplicate = self.client.post(f"/api/events/{self.event_id}/register", headers={"Authorization": "Bearer student-one-token"})
            after = self.client.get("/api/notifications?type=registration&limit=100", headers={"Authorization": "Bearer student-one-token"}).get_json()["data"]
        self.assertEqual(duplicate.status_code, 409)
        before_count = sum(self.event_title in item["message"] for item in before)
        after_count = sum(self.event_title in item["message"] for item in after)
        self.assertEqual(before_count, after_count)

    def test_published_update_notifies_active_students_only(self):
        self.assertEqual(self._register(STUDENT_ONE, "student-one-token").status_code, 201)
        with self._auth(STUDENT_TWO, "student"):
            second = self.client.post(f"/api/events/{self.event_id}/register", headers={"Authorization": "Bearer student-two-token"})
            self.assertEqual(second.status_code, 201)
            self.assertEqual(self.client.delete(f"/api/events/{self.event_id}/register", headers={"Authorization": "Bearer student-two-token"}).status_code, 200)

        with self._auth(ORGANIZER, "organizer"):
            with patch("app.routes.events.verify_access_token", return_value=ORGANIZER), patch("app.routes.events._load_profile", return_value=profile(ORGANIZER, "organizer")):
                updated = self.client.put(
                    f"/api/events/{self.event_id}",
                    json={"title": f"Updated {self.event_title}"},
                    headers={"Authorization": "Bearer organizer-token"},
                )
        self.assertEqual(updated.status_code, 200)

        with self._auth(STUDENT_ONE, "student"):
            one = self.client.get("/api/notifications?type=event_update&limit=100", headers={"Authorization": "Bearer student-one-token"}).get_json()["data"]
        with self._auth(STUDENT_TWO, "student"):
            two = self.client.get("/api/notifications?type=event_update&limit=100", headers={"Authorization": "Bearer student-two-token"}).get_json()["data"]
        self.assertTrue(any(self.event_title in item["message"] for item in one))
        self.assertFalse(any(self.event_title in item["message"] for item in two))

    def test_event_cancellation_notifies_active_students_once(self):
        self.assertEqual(self._register(STUDENT_ONE, "student-one-token").status_code, 201)
        with self._auth(ORGANIZER, "organizer"):
            with patch("app.routes.events.verify_access_token", return_value=ORGANIZER), patch("app.routes.events._load_profile", return_value=profile(ORGANIZER, "organizer")):
                cancelled = self.client.patch(f"/api/events/{self.event_id}/cancel", headers={"Authorization": "Bearer organizer-token"})
                repeated = self.client.patch(f"/api/events/{self.event_id}/cancel", headers={"Authorization": "Bearer organizer-token"})
        self.assertEqual(cancelled.status_code, 200)
        self.assertEqual(repeated.status_code, 422)
        with self._auth(STUDENT_ONE, "student"):
            items = self.client.get("/api/notifications?type=cancellation&limit=100", headers={"Authorization": "Bearer student-one-token"}).get_json()["data"]
        self.assertEqual(sum(self.event_title in item["message"] for item in items), 1)

    def test_read_unread_count_and_owner_protection(self):
        title = f"Read Test {uuid.uuid4()}"
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("insert into notifications (user_id, title, message, type) values (%s, %s, %s, 'system') returning id", (STUDENT_ONE["id"], title, title))
                notification_id = str(cursor.fetchone()[0])
                cursor.execute("insert into notifications (user_id, title, message, type) values (%s, %s, %s, 'system')", (STUDENT_TWO["id"], title, title))

        with self._auth(STUDENT_ONE, "student"):
            count = self.client.get("/api/notifications/unread-count", headers={"Authorization": "Bearer student-one-token"})
            marked = self.client.patch(f"/api/notifications/{notification_id}/read", headers={"Authorization": "Bearer student-one-token"})
            all_read = self.client.patch("/api/notifications/read-all", headers={"Authorization": "Bearer student-one-token"})
        self.assertEqual(count.status_code, 200)
        self.assertEqual(marked.status_code, 200)
        self.assertTrue(marked.get_json()["data"]["is_read"])
        self.assertGreaterEqual(all_read.get_json()["data"]["updated_count"], 0)

        with self._auth(STUDENT_TWO, "student"):
            forbidden = self.client.patch(f"/api/notifications/{notification_id}/read", headers={"Authorization": "Bearer student-two-token"})
        self.assertEqual(forbidden.status_code, 404)

        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("delete from notifications where title = %s", (title,))

    def test_unauthenticated_notifications_are_rejected(self):
        self.assertEqual(self.client.get("/api/notifications").status_code, 401)
        self.assertEqual(self.client.get("/api/notifications/unread-count").status_code, 401)
