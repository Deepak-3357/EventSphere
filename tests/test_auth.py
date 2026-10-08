import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import create_app  # noqa: E402


class AuthRouteTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app = create_app()
        app.config.update(TESTING=True)
        cls.client = app.test_client()

    def test_public_config_does_not_expose_database_credentials(self):
        response = self.client.get("/api/config")
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertIn("supabaseUrl", body)
        self.assertIn("supabasePublishableKey", body)
        self.assertNotIn("SUPABASE_DB_PASSWORD", body)

    def test_protected_routes_require_bearer_token(self):
        for route in ("/api/auth/me", "/api/auth/student-test", "/api/auth/organizer-test", "/api/auth/admin-test"):
            with self.subTest(route=route):
                self.assertEqual(self.client.get(route).status_code, 401)

    def test_invalid_token_is_rejected(self):
        with patch("app.routes.auth.verify_access_token", return_value=None):
            response = self.client.get(
                "/api/auth/me", headers={"Authorization": "Bearer invalid-test-token"}
            )
        self.assertEqual(response.status_code, 401)

    def test_rbac_uses_verified_profile_role_not_request_body(self):
        verified_user = {"id": "00000000-0000-0000-0000-000000000001", "email": "student@example.test"}
        student_profile = {"id": verified_user["id"], "full_name": "Student", "role": "student"}
        with patch("app.routes.auth.verify_access_token", return_value=verified_user), patch(
            "app.routes.auth._load_profile", return_value=student_profile
        ):
            student_response = self.client.get(
                "/api/auth/student-test",
                headers={"Authorization": "Bearer valid-test-token"},
                json={"role": "admin"},
            )
            admin_response = self.client.get(
                "/api/auth/admin-test",
                headers={"Authorization": "Bearer valid-test-token"},
            )

        self.assertEqual(student_response.status_code, 200)
        self.assertEqual(admin_response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
