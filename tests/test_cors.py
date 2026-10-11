"""Response-level regression tests for the browser origin allowlist."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import create_app  # noqa: E402


class CorsAllowlistTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app = create_app()
        app.config.update(
            TESTING=True,
            FRONTEND_ORIGIN="https://configured.example",
            FRONTEND_ALLOWED_ORIGINS="https://preview.example.com, https://staging.example.com/",
        )
        cls.client = app.test_client()

    def response(self, origin=None, method="GET"):
        headers = {"Origin": origin} if origin is not None else {}
        return self.client.open("/api/health", method=method, headers=headers)

    def test_production_origin_is_always_allowed(self):
        response = self.response("https://eventsphere-395t.onrender.com")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), "https://eventsphere-395t.onrender.com")

    def test_configured_origins_are_allowed_exactly(self):
        response = self.response("https://preview.example.com")
        self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), "https://preview.example.com")
        self.assertEqual(self.response("https://staging.example.com").headers.get("Access-Control-Allow-Origin"), "https://staging.example.com")
        self.assertEqual(self.response("https://configured.example").headers.get("Access-Control-Allow-Origin"), "https://configured.example")

    def test_unknown_and_lookalike_origins_are_not_reflected(self):
        for origin in (
            "https://unknown.example",
            "https://eventsphere-395t.onrender.com.evil.example",
            "https://evil.example/eventsphere-395t.onrender.com",
            "https://preview.example.com.attacker.example",
        ):
            response = self.response(origin)
            self.assertNotIn("Access-Control-Allow-Origin", response.headers, origin)

    def test_missing_origin_is_handled_without_cors_headers(self):
        response = self.response()
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Access-Control-Allow-Origin", response.headers)

    def test_allowed_preflight_includes_required_headers(self):
        response = self.client.options(
            "/api/health",
            headers={
                "Origin": "https://preview.example.com",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Authorization, Content-Type",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), "https://preview.example.com")
        self.assertIn("Authorization", response.headers.get("Access-Control-Allow-Headers", ""))
        self.assertIn("Content-Type", response.headers.get("Access-Control-Allow-Headers", ""))
        self.assertIn("POST", response.headers.get("Access-Control-Allow-Methods", ""))
        self.assertEqual(response.headers.get("Vary"), "Origin")

    def test_disallowed_preflight_is_not_granted_access(self):
        response = self.client.options(
            "/api/health",
            headers={"Origin": "https://unknown.example", "Access-Control-Request-Method": "POST"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Access-Control-Allow-Origin", response.headers)
        self.assertNotIn("Access-Control-Allow-Headers", response.headers)


if __name__ == "__main__":
    unittest.main()
