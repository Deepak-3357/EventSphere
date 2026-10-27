"""Database-free regression tests for safe public catalog failures."""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from psycopg import DatabaseError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import create_app  # noqa: E402


class CatalogApiTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app = create_app()
        app.config.update(TESTING=True)
        cls.client = app.test_client()

    def test_venue_list_success_uses_data_array(self):
        venues = [{"id": "venue-1", "name": "Main Hall", "location": "Campus", "capacity": 100, "is_active": True}]
        with patch("app.routes.catalog.venue_service.list_venues", return_value=venues):
            response = self.client.get("/api/venues")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"data": venues, "success": True})

    def test_venue_database_failure_is_safe_json(self):
        with patch("app.routes.catalog.venue_service.list_venues", side_effect=DatabaseError("database details must stay server-side")):
            response = self.client.get("/api/venues")
        self.assertEqual(response.status_code, 500)
        body = response.get_json()
        self.assertEqual(body["error"]["code"], "DATABASE_ERROR")
        self.assertEqual(body["error"]["message"], "The venue request could not be completed.")
        self.assertNotIn("database details", response.get_data(as_text=True))


class FrontendFailureHandlingTestCase(unittest.TestCase):
    def test_organizer_event_and_venue_loading_are_independent_and_validated(self):
        source = (ROOT / "frontend/organizer/events/manage.js").read_text(encoding="utf-8")
        self.assertIn("Array.isArray(body.data)", source)
        self.assertIn("Promise.all([loadLookups(), loadEvents()])", source)
        self.assertIn("Venue information is temporarily unavailable.", source)
        self.assertIn("setVenueLookupState(false)", source)

    def test_venue_page_disables_booking_and_offers_retry_on_failure(self):
        source = (ROOT / "frontend/assets/js/venues.js").read_text(encoding="utf-8")
        page = (ROOT / "frontend/venues/index.html").read_text(encoding="utf-8")
        self.assertIn("Array.isArray(loadedVenues)", source)
        self.assertIn("setBookingEnabled(false)", source)
        self.assertIn("retryVenueButton", source)
        self.assertIn('id="retryVenueButton"', page)


if __name__ == "__main__":
    unittest.main()
