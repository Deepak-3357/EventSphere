"""Database-free authorization and response tests for venue management."""

import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import create_app  # noqa: E402
from app.services import venue_service  # noqa: E402


USERS = {
    "student": {"id": "00000000-0000-0000-0000-000000000001", "email": "student@example.test"},
    "organizer": {"id": "00000000-0000-0000-0000-000000000003", "email": "organizer@example.test"},
    "admin": {"id": "00000000-0000-0000-0000-000000000005", "email": "admin@example.test"},
}


def profile(role):
    return {"id": USERS[role]["id"], "full_name": role.title(), "role": role, "is_master_admin": role == "admin"}


class VenueApiTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app = create_app()
        app.config.update(TESTING=True)
        cls.client = app.test_client()

    def auth(self, role):
        user = USERS[role]
        return patch.multiple(
            "app.routes.auth",
            verify_access_token=lambda token: user,
            _load_profile=lambda user_id: profile(role),
        )

    def test_organizer_calendar_is_authorized_and_student_is_denied(self):
        with self.auth("organizer"), patch("app.routes.venues.venue_service.list_venues", return_value=[]):
            with patch("app.routes.venues.venue_service.availability", return_value={"venue": {}, "date": "2099-12-01", "events": [], "bookings": []}) as availability:
                response = self.client.get("/api/venues/calendar?date=2099-12-01", headers={"Authorization": "Bearer organizer-token"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["success"])
        availability.assert_not_called()
        with self.auth("student"):
            response = self.client.get("/api/venues/calendar?date=2099-12-01", headers={"Authorization": "Bearer student-token"})
        self.assertEqual(response.status_code, 403)

    def test_calendar_and_direct_availability_are_detail_scoped_by_role(self):
        venue = {"id": "20000000-0000-0000-0000-000000000001"}
        result = {"venue": {}, "date": "2099-12-01", "events": [], "bookings": []}
        with self.auth("organizer"), patch("app.routes.venues.venue_service.list_venues", return_value=[venue]), patch("app.routes.venues.venue_service.availability", return_value=result) as availability:
            response = self.client.get("/api/venues/calendar?date=2099-12-01", headers={"Authorization": "Bearer organizer-token"})
        self.assertEqual(response.status_code, 200)
        availability.assert_called_once_with(venue["id"], "2099-12-01", include_details=False)

        with self.auth("admin"), patch("app.routes.venues.venue_service.list_venues", return_value=[venue]), patch("app.routes.venues.venue_service.availability", return_value=result) as availability:
            response = self.client.get("/api/venues/calendar?date=2099-12-01", headers={"Authorization": "Bearer admin-token"})
        self.assertEqual(response.status_code, 200)
        availability.assert_called_once_with(venue["id"], "2099-12-01", include_details=True)

        with self.auth("organizer"), patch("app.routes.venues.venue_service.availability", return_value=result) as availability:
            response = self.client.get(f"/api/venues/{venue['id']}/availability?date=2099-12-01", headers={"Authorization": "Bearer organizer-token"})
        self.assertEqual(response.status_code, 200)
        availability.assert_called_once_with(venue["id"], "2099-12-01", include_details=False)

        with self.auth("admin"), patch("app.routes.venues.venue_service.availability", return_value=result) as availability:
            response = self.client.get(f"/api/venues/{venue['id']}/availability?date=2099-12-01", headers={"Authorization": "Bearer admin-token"})
        self.assertEqual(response.status_code, 200)
        availability.assert_called_once_with(venue["id"], "2099-12-01", include_details=True)

    def test_organizer_cannot_read_another_users_booking_but_can_read_own(self):
        booking = {"id": "50000000-0000-0000-0000-000000000001", "requester_id": USERS["admin"]["id"], "title": "Private"}
        with self.auth("organizer"), patch("app.routes.venues.venue_service.get_booking", return_value=booking):
            response = self.client.get(f"/api/venues/bookings/{booking['id']}", headers={"Authorization": "Bearer organizer-token"})
        self.assertEqual(response.status_code, 404)

        booking["requester_id"] = USERS["organizer"]["id"]
        with self.auth("organizer"), patch("app.routes.venues.venue_service.get_booking", return_value=booking):
            response = self.client.get(f"/api/venues/bookings/{booking['id']}", headers={"Authorization": "Bearer organizer-token"})
        self.assertEqual(response.status_code, 200)

        with self.auth("admin"), patch("app.routes.venues.venue_service.get_booking", return_value=booking):
            response = self.client.get(f"/api/venues/bookings/{booking['id']}", headers={"Authorization": "Bearer admin-token"})
        self.assertEqual(response.status_code, 200)

    def test_organizer_can_read_calendar_and_use_availability_check(self):
        with self.auth("organizer"):
            with patch("app.routes.venues.venue_service.list_venues", return_value=[]):
                response = self.client.get("/api/venues/calendar?date=2099-12-01", headers={"Authorization": "Bearer organizer-token"})
        self.assertEqual(response.status_code, 200)
        with self.auth("organizer"), patch("app.routes.venues.venue_service.restricted_availability", return_value={"available": True, "reason": "available"}):
            response = self.client.post("/api/venues/availability-check", json={"venue_id": "20000000-0000-0000-0000-000000000001", "date": "2099-12-01", "start_time": "10:00", "end_time": "11:00"}, headers={"Authorization": "Bearer organizer-token"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["data"]["available"], True)

    def test_booking_success_and_conflict_response(self):
        booking = {"id": "50000000-0000-0000-0000-000000000001", "status": "confirmed"}
        with self.auth("organizer"), patch("app.routes.venues.venue_service.create_booking", return_value=booking):
            response = self.client.post("/api/venues/bookings", json={"venue_id": "20000000-0000-0000-0000-000000000001", "title": "Organizer seminar", "date": "2099-12-01", "start_time": "10:00", "end_time": "11:00"}, headers={"Authorization": "Bearer organizer-token"})
        self.assertEqual(response.status_code, 201)
        with self.auth("organizer"), patch("app.routes.venues.venue_service.create_booking", side_effect=venue_service.VenueServiceError("VENUE_CONFLICT", "The venue is already booked", 409)):
            response = self.client.post("/api/venues/bookings", json={"venue_id": "20000000-0000-0000-0000-000000000001", "title": "Conflict", "date": "2099-12-01", "start_time": "10:00", "end_time": "11:00"}, headers={"Authorization": "Bearer organizer-token"})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["error"]["code"], "VENUE_CONFLICT")

    def test_admin_can_manage_venues_and_students_cannot_book(self):
        with self.auth("admin"), patch("app.routes.venues.venue_service.list_venues", return_value=[]):
            response = self.client.get("/api/venues/manage", headers={"Authorization": "Bearer admin-token"})
        self.assertEqual(response.status_code, 200)
        with self.auth("student"):
            response = self.client.post("/api/venues/bookings", json={}, headers={"Authorization": "Bearer student-token"})
        self.assertEqual(response.status_code, 403)


class VenueValidationTestCase(unittest.TestCase):
    def test_overnight_and_invalid_slots_are_rejected(self):
        for payload in (
            {"date": "2099-12-01", "start_time": "11:00", "end_time": "10:00"},
            {"date": "not-a-date", "start_time": "10:00", "end_time": "11:00"},
        ):
            with self.assertRaises(venue_service.VenueServiceError):
                venue_service.parse_slot(payload)


class AvailabilityPrivacyTestCase(unittest.TestCase):
    class Cursor:
        def __init__(self):
            self.query_number = 0

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def execute(self, *_):
            self.query_number += 1

        def fetchone(self):
            return ("20000000-0000-0000-0000-000000000001", "Main Hall", "Campus", 100, True)

        def fetchall(self):
            if self.query_number == 2:
                return [(datetime(2099, 12, 1, 4, 30), datetime(2099, 12, 1, 5, 30))]
            return [("2099-12-01", "10:00:00", "11:00:00")]

    class Connection:
        def __init__(self, cursor):
            self.cursor_value = cursor

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def cursor(self):
            return self.cursor_value

    def test_minimal_availability_contains_ranges_only(self):
        cursor = self.Cursor()
        with patch("app.services.venue_service.get_connection", return_value=self.Connection(cursor)):
            result = venue_service.availability("20000000-0000-0000-0000-000000000001", "2099-12-01", include_details=False)
        self.assertEqual(result["bookings"], [{"start_at": "2099-12-01T04:30:00", "end_at": "2099-12-01T05:30:00"}])
        self.assertEqual(result["events"], [{"date": "2099-12-01", "start_time": "10:00:00", "end_time": "11:00:00"}])
        self.assertNotIn("id", result["bookings"][0])
        self.assertNotIn("title", result["bookings"][0])
        self.assertNotIn("id", result["events"][0])
        self.assertNotIn("title", result["events"][0])
        self.assertNotIn("status", result["events"][0])

    def test_detailed_availability_remains_available_for_admin(self):
        class DetailedCursor(self.Cursor):
            def fetchall(self):
                if self.query_number == 2:
                    return [("50000000-0000-0000-0000-000000000002", "Private booking", datetime(2099, 12, 1, 4, 30), datetime(2099, 12, 1, 5, 30))]
                return [("60000000-0000-0000-0000-000000000003", "Private event", "2099-12-01", "10:00:00", "11:00:00", "published")]

        cursor = DetailedCursor()
        with patch("app.services.venue_service.get_connection", return_value=self.Connection(cursor)):
            result = venue_service.availability("20000000-0000-0000-0000-000000000001", "2099-12-01", include_details=True)
        self.assertEqual(result["bookings"][0]["title"], "Private booking")
        self.assertEqual(result["events"][0]["title"], "Private event")


if __name__ == "__main__":
    unittest.main()
