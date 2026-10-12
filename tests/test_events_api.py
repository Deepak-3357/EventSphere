import sys
import unittest
import uuid
from xml.etree import ElementTree
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import create_app  # noqa: E402
from app.db import get_connection  # noqa: E402
from integration_support import require_integration_database, resolve_profile_id  # noqa: E402


ORGANIZER = {"id": resolve_profile_id("rohan.organizer@example.test", "00000000-0000-0000-0000-000000000003"), "email": "organizer@example.test"}
OTHER_ORGANIZER = {"id": "00000000-0000-0000-0000-000000000004", "email": "other@example.test"}
STUDENT = {"id": "00000000-0000-0000-0000-000000000001", "email": "student@example.test"}
ADMIN = {"id": resolve_profile_id("admin@example.test", "00000000-0000-0000-0000-000000000005"), "email": "admin@example.test"}


def profile(user, role):
    return {"id": user["id"], "full_name": role.title(), "role": role}


class EventApiTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        require_integration_database()
        app = create_app()
        app.config.update(TESTING=True)
        cls.client = app.test_client()

    def setUp(self):
        self.created_ids = []

    def tearDown(self):
        if self.created_ids:
            with get_connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute("delete from events where id = any(%s)", (self.created_ids,))

    def _auth(self, user, role):
        return patch.multiple(
            "app.routes.auth",
            verify_access_token=lambda token: user,
            _load_profile=lambda user_id: profile(user, role),
        )

    def test_public_catalog_and_published_event_listing(self):
        events = self.client.get("/api/events?limit=100")
        categories = self.client.get("/api/categories")
        venues = self.client.get("/api/venues")

        self.assertEqual(events.status_code, 200)
        self.assertTrue(events.get_json()["success"])
        self.assertTrue(all(item["status"] == "published" for item in events.get_json()["data"]))
        self.assertEqual(categories.status_code, 200)
        self.assertEqual(venues.status_code, 200)

    def test_public_xml_catalog_is_valid_and_published_only(self):
        response = self.client.get("/api/events/export.xml")
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/xml", response.content_type)
        root = ElementTree.fromstring(response.data)
        self.assertEqual(root.tag, "events")
        self.assertTrue(all(item.findtext("status") == "published" for item in root.findall("event")))

    def test_organizer_create_publish_and_search(self):
        title = f"API Test Event {uuid.uuid4()}"
        payload = {
            "title": title,
            "description": "An event created by the Phase 4 API test.",
            "category_id": "10000000-0000-0000-0000-000000000001",
            "venue_id": "20000000-0000-0000-0000-000000000004",
            "event_date": "2099-12-01",
            "start_time": "14:00",
            "end_time": "16:00",
            "capacity": 25,
            "registration_deadline": "2099-11-30T18:00:00+05:30",
            "status": "draft",
        }
        with self._auth(ORGANIZER, "organizer"):
            with patch("app.routes.events.verify_access_token", return_value=ORGANIZER), patch(
                "app.routes.events._load_profile", return_value=profile(ORGANIZER, "organizer")
            ):
                response = self.client.post(
                    "/api/events",
                    json=payload,
                    headers={"Authorization": "Bearer organizer-test-token"},
                )
                self.assertEqual(response.status_code, 201)
                event = response.get_json()["data"]
                self.created_ids.append(event["id"])
                self.assertEqual(event["organizer"]["id"], ORGANIZER["id"])

                published = self.client.patch(
                    f"/api/events/{event['id']}/publish",
                    headers={"Authorization": "Bearer organizer-test-token"},
                )
                self.assertEqual(published.status_code, 200)
                self.assertEqual(published.get_json()["data"]["status"], "published")

                search = self.client.get("/api/events", query_string={"search": title, "limit": 1})
                self.assertEqual(search.status_code, 200)
                self.assertEqual(len(search.get_json()["data"]), 1)

    def test_student_cannot_create_and_organizer_ownership_is_enforced(self):
        with self._auth(STUDENT, "student"):
            response = self.client.post(
                "/api/events",
                json={"title": "Should fail"},
                headers={"Authorization": "Bearer student-test-token"},
            )
        self.assertEqual(response.status_code, 403)

        with self._auth(ORGANIZER, "organizer"):
            with patch("app.routes.events.verify_access_token", return_value=ORGANIZER), patch(
                "app.routes.events._load_profile", return_value=profile(ORGANIZER, "organizer")
            ):
                created = self.client.post(
                    "/api/events",
                    json={
                        "title": f"Ownership Test {uuid.uuid4()}",
                        "description": "Ownership test event",
                        "category_id": "10000000-0000-0000-0000-000000000001",
                        "venue_id": "20000000-0000-0000-0000-000000000004",
                        "event_date": "2099-12-02",
                        "start_time": "10:00",
                        "end_time": "11:00",
                        "capacity": 10,
                        "registration_deadline": "2099-12-01T18:00:00+05:30",
                    },
                    headers={"Authorization": "Bearer organizer-test-token"},
                )
                self.assertEqual(created.status_code, 201)
                event_id = created.get_json()["data"]["id"]
                self.created_ids.append(event_id)

        with self._auth(OTHER_ORGANIZER, "organizer"):
            with patch("app.routes.events.verify_access_token", return_value=OTHER_ORGANIZER), patch(
                "app.routes.events._load_profile", return_value=profile(OTHER_ORGANIZER, "organizer")
            ):
                response = self.client.put(
                    f"/api/events/{event_id}",
                    json={"title": "Unauthorized edit"},
                    headers={"Authorization": "Bearer other-organizer-test-token"},
                )
        self.assertEqual(response.status_code, 403)

    def test_server_validation_rejects_invalid_time_and_capacity(self):
        with self._auth(ORGANIZER, "organizer"):
            with patch("app.routes.events.verify_access_token", return_value=ORGANIZER), patch(
                "app.routes.events._load_profile", return_value=profile(ORGANIZER, "organizer")
            ):
                response = self.client.post(
                    "/api/events",
                    json={
                        "title": "Invalid event",
                        "category_id": "10000000-0000-0000-0000-000000000001",
                        "venue_id": "20000000-0000-0000-0000-000000000004",
                        "event_date": "2099-12-02",
                        "start_time": "12:00",
                        "end_time": "11:00",
                        "capacity": 0,
                        "registration_deadline": "2099-12-01T18:00:00+05:30",
                    },
                    headers={"Authorization": "Bearer organizer-test-token"},
                )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.get_json()["success"], False)

    def test_admin_can_manage_and_student_cannot_modify(self):
        with self._auth(ADMIN, "admin"):
            with patch("app.routes.events.verify_access_token", return_value=ADMIN), patch(
                "app.routes.events._load_profile", return_value=profile(ADMIN, "admin")
            ):
                created = self.client.post(
                    "/api/events",
                    json={
                        "title": f"Admin Test {uuid.uuid4()}",
                        "description": "Admin-managed event",
                        "category_id": "10000000-0000-0000-0000-000000000001",
                        "venue_id": "20000000-0000-0000-0000-000000000004",
                        "event_date": "2099-12-03",
                        "start_time": "10:00",
                        "end_time": "11:00",
                        "capacity": 10,
                        "registration_deadline": "2099-12-02T18:00:00+05:30",
                    },
                    headers={"Authorization": "Bearer admin-test-token"},
                )
                self.assertEqual(created.status_code, 201)
                event_id = created.get_json()["data"]["id"]
                self.created_ids.append(event_id)
                updated = self.client.put(
                    f"/api/events/{event_id}",
                    json={"title": "Updated by admin"},
                    headers={"Authorization": "Bearer admin-test-token"},
                )
                self.assertEqual(updated.status_code, 200)
                cancelled = self.client.patch(
                    f"/api/events/{event_id}/cancel",
                    headers={"Authorization": "Bearer admin-test-token"},
                )
                self.assertEqual(cancelled.status_code, 200)

        with self._auth(STUDENT, "student"):
            with patch("app.routes.events.verify_access_token", return_value=STUDENT), patch(
                "app.routes.events._load_profile", return_value=profile(STUDENT, "student")
            ):
                for method, path in (("put", ""), ("delete", ""), ("patch", "/publish"), ("patch", "/cancel")):
                    response = getattr(self.client, method)(
                        f"/api/events/{event_id}{path}",
                        json={"title": "Student edit"} if method == "put" else None,
                        headers={"Authorization": "Bearer student-test-token"},
                    )
                    self.assertEqual(response.status_code, 403)

    def test_draft_faqs_and_partial_edit_preserve_existing_data(self):
        payload = {
            "title": f"FAQ Test {uuid.uuid4()}",
            "description": "Keep this description",
            "category_id": "10000000-0000-0000-0000-000000000001",
            "venue_id": "20000000-0000-0000-0000-000000000004",
            "event_date": "2099-12-04",
            "start_time": "10:00",
            "end_time": "11:00",
            "capacity": 10,
            "registration_deadline": "2099-12-03T18:00:00+05:30",
        }
        with self._auth(ORGANIZER, "organizer"):
            with patch("app.routes.events.verify_access_token", return_value=ORGANIZER), patch(
                "app.routes.events._load_profile", return_value=profile(ORGANIZER, "organizer")
            ):
                created = self.client.post("/api/events", json=payload, headers={"Authorization": "Bearer organizer-test-token"})
                self.assertEqual(created.status_code, 201)
                event = created.get_json()["data"]
                self.created_ids.append(event["id"])
                faq = self.client.post(
                    f"/api/events/{event['id']}/faqs",
                    json={"question": "When?", "answer": "At ten.", "position": 0},
                    headers={"Authorization": "Bearer organizer-test-token"},
                )
                self.assertEqual(faq.status_code, 201)
                listed = self.client.get(f"/api/events/{event['id']}/faqs", headers={"Authorization": "Bearer organizer-test-token"})
                self.assertEqual(listed.status_code, 200)
                self.assertEqual(listed.get_json()["data"][0]["question"], "When?")
                updated = self.client.put(
                    f"/api/events/{event['id']}",
                    json={"title": "Edited title"},
                    headers={"Authorization": "Bearer organizer-test-token"},
                )
                self.assertEqual(updated.status_code, 200)
                self.assertEqual(updated.get_json()["data"]["description"], payload["description"])
                self.assertEqual(self.client.get(f"/api/events/{event['id']}/faqs", headers={"Authorization": "Bearer organizer-test-token"}).get_json()["data"][0]["answer"], "At ten.")

        with self._auth(OTHER_ORGANIZER, "organizer"):
            with patch("app.routes.events.verify_access_token", return_value=OTHER_ORGANIZER), patch(
                "app.routes.events._load_profile", return_value=profile(OTHER_ORGANIZER, "organizer")
            ):
                self.assertEqual(self.client.get(f"/api/events/{event['id']}/faqs", headers={"Authorization": "Bearer other-organizer-test-token"}).status_code, 404)
                self.assertEqual(self.client.post(f"/api/events/{event['id']}/faqs", json={"question": "No", "answer": "No"}, headers={"Authorization": "Bearer other-organizer-test-token"}).status_code, 403)

    def test_unauthenticated_management_requests_are_rejected(self):
        event_id = "30000000-0000-0000-0000-000000000001"
        self.assertEqual(self.client.post("/api/events", json={}).status_code, 401)
        for method, suffix in (("put", ""), ("delete", ""), ("patch", "/publish"), ("patch", "/cancel")):
            response = getattr(self.client, method)(f"/api/events/{event_id}{suffix}", json={"title": "x"} if method == "put" else None)
            self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
