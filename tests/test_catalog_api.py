"""Regression tests for the public category catalog and venue removal."""

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

    def test_category_list_success_uses_data_array(self):
        categories = [{"id": "category-1", "name": "Technology", "description": "Tech events"}]
        with patch("app.routes.catalog.event_service.list_categories", return_value=categories):
            response = self.client.get("/api/categories")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"data": categories, "success": True})

    def test_category_database_failure_is_safe_json(self):
        with patch("app.routes.catalog.event_service.list_categories", side_effect=DatabaseError("database details must stay server-side")):
            response = self.client.get("/api/categories")
        self.assertEqual(response.status_code, 500)
        body = response.get_json()
        self.assertEqual(body["error"]["code"], "DATABASE_ERROR")
        self.assertNotIn("database details", response.get_data(as_text=True))

    def test_venue_api_is_removed(self):
        self.assertEqual(self.client.get("/api/venues").status_code, 404)


class VenueRemovalFrontendTestCase(unittest.TestCase):
    def test_event_management_has_no_venue_lookup_or_failure_dependency(self):
        source = (ROOT / "frontend/organizer/events/manage.js").read_text(encoding="utf-8")
        page = (ROOT / "frontend/organizer/events/index.html").read_text(encoding="utf-8")
        self.assertNotIn("/api/venues", source)
        self.assertNotIn("venue", source.lower())
        self.assertNotIn("venue", page.lower())


if __name__ == "__main__":
    unittest.main()
