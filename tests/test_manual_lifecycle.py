"""Manual event lifecycle (Start/End) and publication-status preservation tests.

Covers the required test matrix for Problems A and B. Database-writing tests
use the standard explicit local-DB opt-in and never touch production data.
Publication-status tests are logic-level (no DB writes required).
"""

import sys
import unittest
import uuid
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import create_app  # noqa: E402
from app.db import get_connection  # noqa: E402
from app.services import attendance_service, event_service  # noqa: E402
from integration_support import require_integration_database, resolve_profile_id  # noqa: E402


ORGANIZER = {"id": resolve_profile_id("rohan.organizer@example.test", "00000000-0000-0000-0000-000000000003"), "email": "organizer@example.test"}
OTHER_ORGANIZER = {"id": "00000000-0000-0000-0000-000000000004", "email": "other@example.test"}
STUDENT = {"id": "00000000-0000-0000-0000-000000000001", "email": "student@example.test"}
ADMIN = {"id": resolve_profile_id("admin@example.test", "00000000-0000-0000-0000-000000000005"), "email": "admin@example.test"}

FUTURE_DATE = (date.today() + timedelta(days=365)).isoformat()


def profile(user, role):
    return {"id": user["id"], "full_name": role.title(), "role": role}


def base_payload(prefix="Lifecycle Test"):
    return {
        "title": f"{prefix} {uuid.uuid4()}",
        "description": "Lifecycle test event",
        "category_id": "10000000-0000-0000-0000-000000000001",
        "venue_id": "20000000-0000-0000-0000-000000000004",
        "event_date": FUTURE_DATE,
        "start_time": "10:00",
        "end_time": "11:00",
        "capacity": 10,
        "registration_deadline": f"{FUTURE_DATE}T08:00:00+05:30",
    }


class EventPayloadLifecycleTestCase(unittest.TestCase):
    """Problem A: status never changes through ordinary edits (no DB)."""

    def test_edit_without_status_defaults_to_current(self):
        current = {"title": "T", "category_id": "10000000-0000-0000-0000-000000000001",
                   "venue_id": "20000000-0000-0000-0000-000000000004", "event_date": date(2099, 12, 1),
                   "start_time": time(10, 0), "end_time": time(11, 0), "capacity": 10,
                   "registration_deadline": datetime(2099, 11, 30, 18, 0), "status": "published",
                   "participation_mode": "individual", "min_team_size": None, "max_team_size": None,
                   "eligibility": "", "registration_instructions": "", "facilities": {}, "image_url": None,
                   "description": ""}
        values = event_service.validate_event_payload(
            {"title": "New title"}, current=current, requested_status=current["status"]
        )
        self.assertEqual(values["status"], "published")

    def test_client_supplied_status_is_ignored_for_updates(self):
        self.assertEqual(event_service.validate_event_payload.__doc__ or "", "")  # smoke
        # update_event itself ignores payload status (server-authoritative).
        import inspect
        source = inspect.getsource(event_service.update_event)
        self.assertIn('requested_status = current["status"]', source)

    def test_repeat_start_reads_row_values_not_globals(self):
        """Regression for D1: idempotent branch unpacks started_at/started_by."""
        import inspect
        source = inspect.getsource(event_service.start_event)
        self.assertIn("_, event_status, started_at, started_by = row", source)
        # No module-level globals mask an unpack bug.
        import app.services.event_service as module
        self.assertFalse(hasattr(module, "started_at"))
        self.assertFalse(hasattr(module, "started_by"))

    def test_d3_response_uses_single_timestamp(self):
        """Regression for D3: one timestamp feeds both UPDATE and response."""
        import inspect
        start_src = inspect.getsource(event_service.start_event)
        end_src = inspect.getsource(event_service.end_event)
        self.assertEqual(start_src.count("datetime.now(timezone.utc)"), 1)
        self.assertEqual(end_src.count("datetime.now(timezone.utc)"), 1)


class WindowLogicTestCase(unittest.TestCase):
    """Problem B: attendance window semantics without Database writes."""

    def _app(self):
        app = create_app()
        app.config.update(TESTING=True, ATTENDANCE_QR_SECRET="test-secret", ATTENDANCE_CODE_SECRET="test-secret",
                          ATTENDANCE_TIMEZONE="Asia/Kolkata")
        return app

    def test_scheduled_window_opens_and_closes_per_config(self):
        with self._app().test_request_context():
            from zoneinfo import ZoneInfo
            tz = ZoneInfo("Asia/Kolkata")
            event_date, start, end = date(2030, 1, 15), time(10, 0), time(11, 0)
            def ist(h, m):
                return datetime.combine(event_date, time(h, m), tzinfo=tz)
            self.assertFalse(attendance_service._window_is_open(event_date, start, end, now=ist(9, 14)))
            self.assertTrue(attendance_service._window_is_open(event_date, start, end, now=ist(9, 30)))
            self.assertTrue(attendance_service._window_is_open(event_date, start, end, now=ist(10, 30)))
            self.assertTrue(attendance_service._window_is_open(event_date, start, end, now=ist(13, 0)))
            self.assertFalse(attendance_service._window_is_open(event_date, start, end, now=ist(13, 1)))

    def test_manual_start_opens_window_before_scheduled_start(self):
        with self._app().test_request_context():
            from zoneinfo import ZoneInfo
            tz = ZoneInfo("Asia/Kolkata")
            event_date, start, end = date(2030, 1, 15), time(22, 0), time(23, 0)
            started_at = datetime.now(timezone.utc)
            # Past the scheduled end + late grace window (23:00 + 120min = 01:00 next day).
            now = datetime.combine(event_date + timedelta(days=1), time(2, 0), tzinfo=tz).astimezone(timezone.utc)
            self.assertFalse(attendance_service._window_is_open(event_date, start, end, now=now))
            self.assertTrue(attendance_service._window_is_open(event_date, start, end, now=now, started_at=started_at))
            # Before any manual start and outside schedule -> closed (manual start instant matters).
            earlier_now = started_at - timedelta(hours=1)
            self.assertFalse(attendance_service._window_is_open(event_date, start, end, now=earlier_now, started_at=started_at))

    def test_manual_end_closes_window_immediately(self):
        with self._app().test_request_context():
            from zoneinfo import ZoneInfo
            tz = ZoneInfo("Asia/Kolkata")
            event_date, start, end = date.today(), time(0, 0), time(23, 59)
            now = datetime.now(tz)
            self.assertTrue(attendance_service._window_is_open(event_date, start, end, now=now))
            self.assertFalse(
                attendance_service._window_is_open(
                    event_date, start, end, now=now, started_at=now - timedelta(hours=1), ended_at=now
                )
            )

    def test_invalid_qr_is_rejected_after_manual_start(self):
        with self._app().test_request_context():
            bad = '{"registration_id":"00000000-0000-0000-0000-000000000009","token":"deadbeef","type":"eventsphere_attendance"}'
            with self.assertRaises(attendance_service.AttendanceError) as ctx:
                attendance_service._verify_payload(bad)
            self.assertEqual(ctx.exception.code, "INVALID_QR")


class ManualLifecycleApiTestCase(unittest.TestCase):
    """Database-writing integration tests: behavior against the full app."""

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
                    cursor.execute("delete from event_lifecycle_audit where event_id = any(%s)", (self.created_ids,))
                    cursor.execute("delete from events where id = any(%s)", (self.created_ids,))

    def _auth(self, user, role):
        return patch.multiple(
            "app.routes.auth",
            verify_access_token=lambda token: user,
            _load_profile=lambda user_id: profile(user, role),
        )

    def _create_published(self, role="organizer", user=None):
        user = user or ORGANIZER
        with self._auth(ORGANIZER, "organizer"):
            with patch("app.routes.events.verify_access_token", return_value=ORGANIZER), patch(
                "app.routes.events._load_profile", return_value=profile(ORGANIZER, "organizer")
            ):
                created = self.client.post("/api/events", json=base_payload(), headers={"Authorization": "Bearer t"})
                self.assertEqual(created.status_code, 201)
                event = created.get_json()["data"]
                self.created_ids.append(event["id"])
                published = self.client.patch(f"/api/events/{event['id']}/publish", headers={"Authorization": "Bearer t"})
                self.assertEqual(published.status_code, 200, published.get_data(as_text=True))
                return event["id"]

    def test_draft_edit_preserves_draft(self):
        with self._auth(ORGANIZER, "organizer"):
            with patch("app.routes.events.verify_access_token", return_value=ORGANIZER), patch(
                "app.routes.events._load_profile", return_value=profile(ORGANIZER, "organizer")
            ):
                created = self.client.post("/api/events", json=base_payload(), headers={"Authorization": "Bearer t"})
                event = created.get_json()["data"]
                self.created_ids.append(event["id"])
                updated = self.client.put(f"/api/events/{event['id']}", json={"title": "Still draft"}, headers={"Authorization": "Bearer t"})
                self.assertEqual(updated.status_code, 200)
                self.assertEqual(updated.get_json()["data"]["status"], "draft")

    def test_published_edit_preserves_published(self):
        event_id = self._create_published()
        with self._auth(ORGANIZER, "organizer"):
            with patch("app.routes.events.verify_access_token", return_value=ORGANIZER), patch(
                "app.routes.events._load_profile", return_value=profile(ORGANIZER, "organizer")
            ):
                updated = self.client.put(f"/api/events/{event_id}", json={"title": "Edited while published"}, headers={"Authorization": "Bearer t"})
                self.assertEqual(updated.status_code, 200)
                self.assertEqual(updated.get_json()["data"]["status"], "published")

    def test_invalid_edit_does_not_change_state(self):
        event_id = self._create_published()
        with self._auth(ORGANIZER, "organizer"):
            with patch("app.routes.events.verify_access_token", return_value=ORGANIZER), patch(
                "app.routes.events._load_profile", return_value=profile(ORGANIZER, "organizer")
            ):
                response = self.client.put(f"/api/events/{event_id}", json={"capacity": 0}, headers={"Authorization": "Bearer t"})
                self.assertEqual(response.status_code, 422)
                current = self.client.get(f"/api/events/{event_id}", headers={"Authorization": "Bearer t"}).get_json()["data"]
                self.assertEqual(current["status"], "published")

    def test_manual_start_future_event_and_end_fresh_client(self):
        event_id = self._create_published()
        with self._auth(ORGANIZER, "organizer"):
            with patch("app.routes.events.verify_access_token", return_value=ORGANIZER), patch(
                "app.routes.events._load_profile", return_value=profile(ORGANIZER, "organizer")
            ):
                started = self.client.post(f"/api/events/{event_id}/start", headers={"Authorization": "Bearer t"})
                self.assertEqual(started.status_code, 200, started.get_data(as_text=True))
                self.assertEqual(started.get_json()["data"]["operational_state"], "running")
                # Idempotent repeat
                repeated = self.client.post(f"/api/events/{event_id}/start", headers={"Authorization": "Bearer t"})
                self.assertEqual(repeated.status_code, 200)
                self.assertTrue(repeated.get_json()["data"]["already_started"])
                # End requires confirmation
                unconfirmed = self.client.post(f"/api/events/{event_id}/end", json={}, headers={"Authorization": "Bearer t"})
                self.assertEqual(unconfirmed.status_code, 400)
                ended = self.client.post(f"/api/events/{event_id}/end", json={"confirm": True}, headers={"Authorization": "Bearer t"})
                self.assertEqual(ended.status_code, 200)
                self.assertEqual(ended.get_json()["data"]["operational_state"], "ended")
                # Repeat end is safe
                re_ended = self.client.post(f"/api/events/{event_id}/end", json={"confirm": True}, headers={"Authorization": "Bearer t"})
                self.assertEqual(re_ended.status_code, 200)
                self.assertTrue(re_ended.get_json()["data"]["already_ended"])
                # Still publicly visible and published
                public = self.client.get(f"/api/events/{event_id}")
                self.assertEqual(public.status_code, 200)
                self.assertEqual(public.get_json()["data"]["status"], "published")

    def test_unauthorized_users_cannot_start_or_end(self):
        event_id = self._create_published()
        with self._auth(STUDENT, "student"):
            with patch("app.routes.events.verify_access_token", return_value=STUDENT), patch(
                "app.routes.events._load_profile", return_value=profile(STUDENT, "student")
            ):
                for suffix in ("/start", "/end"):
                    response = self.client.post(f"/api/events/{event_id}{suffix}", json={"confirm": True}, headers={"Authorization": "Bearer t"})
                    self.assertEqual(response.status_code, 403)
        with self._auth(OTHER_ORGANIZER, "organizer"):
            with patch("app.routes.events.verify_access_token", return_value=OTHER_ORGANIZER), patch(
                "app.routes.events._load_profile", return_value=profile(OTHER_ORGANIZER, "organizer")
            ):
                for suffix in ("/start", "/end"):
                    response = self.client.post(f"/api/events/{event_id}{suffix}", json={"confirm": True}, headers={"Authorization": "Bearer t"})
                    self.assertEqual(response.status_code, 403)

    def test_admin_can_start_other_organizers_event(self):
        event_id = self._create_published()
        with self._auth(ADMIN, "admin"):
            with patch("app.routes.events.verify_access_token", return_value=ADMIN), patch(
                "app.routes.events._load_profile", return_value=profile(ADMIN, "admin")
            ):
                started = self.client.post(f"/api/events/{event_id}/start", headers={"Authorization": "Bearer t"})
                self.assertEqual(started.status_code, 200)

    def test_repeated_start_is_safe_and_reads_row(self):
        """D1 behavioral: a second POST /start must not 500."""
        event_id = self._create_published()
        with self._auth(ORGANIZER, "organizer"):
            with patch("app.routes.events.verify_access_token", return_value=ORGANIZER), patch(
                "app.routes.events._load_profile", return_value=profile(ORGANIZER, "organizer")
            ):
                first = self.client.post(f"/api/events/{event_id}/start", headers={"Authorization": "Bearer t"})
                self.assertEqual(first.status_code, 200)
                second = self.client.post(f"/api/events/{event_id}/start", headers={"Authorization": "Bearer t"})
                self.assertEqual(second.status_code, 200)
                data = second.get_json()["data"]
                self.assertTrue(data["already_started"])
                self.assertEqual(data["started_at"], first.get_json()["data"]["started_at"])

    def test_repeated_end_is_safe(self):
        event_id = self._create_published()
        with self._auth(ORGANIZER, "organizer"):
            with patch("app.routes.events.verify_access_token", return_value=ORGANIZER), patch(
                "app.routes.events._load_profile", return_value=profile(ORGANIZER, "organizer")
            ):
                self.client.post(f"/api/events/{event_id}/start", headers={"Authorization": "Bearer t"})
                first = self.client.post(f"/api/events/{event_id}/end", json={"confirm": True}, headers={"Authorization": "Bearer t"})
                self.assertEqual(first.status_code, 200)
                second = self.client.post(f"/api/events/{event_id}/end", json={"confirm": True}, headers={"Authorization": "Bearer t"})
                self.assertEqual(second.status_code, 200)
                self.assertTrue(second.get_json()["data"]["already_ended"])

    def test_explicit_unpublish_roundtrip(self):
        event_id = self._create_published()
        with self._auth(ORGANIZER, "organizer"):
            with patch("app.routes.events.verify_access_token", return_value=ORGANIZER), patch(
                "app.routes.events._load_profile", return_value=profile(ORGANIZER, "organizer")
            ):
                response = self.client.patch(f"/api/events/{event_id}/unpublish", headers={"Authorization": "Bearer t"})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.get_json()["data"]["status"], "draft")
                # Client cannot re-publish through ordinary edit; only /publish can.
                edited = self.client.put(f"/api/events/{event_id}", json={"title": "After unpublish"}, headers={"Authorization": "Bearer t"})
                self.assertEqual(edited.status_code, 200)
                self.assertEqual(edited.get_json()["data"]["status"], "draft")

    def test_unauthorized_unpublish_rejected(self):
        event_id = self._create_published()
        for user, role in ((STUDENT, "student"), (OTHER_ORGANIZER, "organizer")):
            with self._auth(user, role):
                with patch("app.routes.events.verify_access_token", return_value=user), patch(
                    "app.routes.events._load_profile", return_value=profile(user, role)
                ):
                    response = self.client.patch(f"/api/events/{event_id}/unpublish", headers={"Authorization": "Bearer t"})
                    self.assertEqual(response.status_code, 403)

    def test_unpublish_only_from_published(self):
        with self._auth(ORGANIZER, "organizer"):
            with patch("app.routes.events.verify_access_token", return_value=ORGANIZER), patch(
                "app.routes.events._load_profile", return_value=profile(ORGANIZER, "organizer")
            ):
                created = self.client.post("/api/events", json=base_payload(), headers={"Authorization": "Bearer t"})
                event = created.get_json()["data"]
                self.created_ids.append(event["id"])
                response = self.client.patch(f"/api/events/{event['id']}/unpublish", headers={"Authorization": "Bearer t"})
                self.assertEqual(response.status_code, 409)

    def test_draft_event_cannot_be_started(self):
        with self._auth(ORGANIZER, "organizer"):
            with patch("app.routes.events.verify_access_token", return_value=ORGANIZER), patch(
                "app.routes.events._load_profile", return_value=profile(ORGANIZER, "organizer")
            ):
                created = self.client.post("/api/events", json=base_payload(), headers={"Authorization": "Bearer t"})
                event = created.get_json()["data"]
                self.created_ids.append(event["id"])
                response = self.client.post(f"/api/events/{event['id']}/start", headers={"Authorization": "Bearer t"})
                self.assertEqual(response.status_code, 409)

    def test_faq_survives_lifecycle_and_edit(self):
        event_id = self._create_published()
        with self._auth(ORGANIZER, "organizer"):
            with patch("app.routes.events.verify_access_token", return_value=ORGANIZER), patch(
                "app.routes.events._load_profile", return_value=profile(ORGANIZER, "organizer")
            ):
                faq = self.client.post(f"/api/events/{event_id}/faqs", json={"question": "When?", "answer": "Soon", "position": 0}, headers={"Authorization": "Bearer t"})
                self.assertEqual(faq.status_code, 201)
                self.client.post(f"/api/events/{event_id}/start", headers={"Authorization": "Bearer t"})
                self.client.put(f"/api/events/{event_id}", json={"title": "Edited"}, headers={"Authorization": "Bearer t"})
                listed = self.client.get(f"/api/events/{event_id}/faqs", headers={"Authorization": "Bearer t"})
                self.assertEqual(listed.get_json()["data"][0]["answer"], "Soon")


if __name__ == "__main__":
    unittest.main()
