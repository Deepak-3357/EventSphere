"""Static checks for the plain-browser frontend API configuration."""

from pathlib import Path
import unittest


AUTH_CLIENT = Path(__file__).resolve().parents[1] / "frontend" / "assets" / "js" / "auth-client.js"


class FrontendApiConfigTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = AUTH_CLIENT.read_text(encoding="utf-8")

    def test_production_and_local_defaults_are_explicit(self):
        self.assertIn('"https://eventspherebackend-azkp.onrender.com"', self.source)
        self.assertIn('"http://127.0.0.1:5000"', self.source)
        self.assertIn("window.location.hostname", self.source)

    def test_runtime_override_is_preserved(self):
        self.assertIn("window.EVENTSPHERE_API_BASE_URL || defaultEventSphereApiBase", self.source)

    def test_api_calls_use_the_shared_url_helper(self):
        self.assertIn("fetch(apiUrl(\"/api/config\"))", self.source)
        self.assertIn("fetch(apiUrl(path)", self.source)


if __name__ == "__main__":
    unittest.main()
