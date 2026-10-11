"""Regression checks for verified role-based home navigation and protection."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"


class RoleNavigationRegressionTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.auth_client = (FRONTEND / "assets/js/auth-client.js").read_text(encoding="utf-8")
        cls.dashboard = (FRONTEND / "assets/js/dashboard.js").read_text(encoding="utf-8")
        cls.protected_dashboard = (FRONTEND / "assets/js/protected-dashboard.js").read_text(encoding="utf-8")
        cls.backend_dashboard = (ROOT / "backend/app/routes/dashboard.py").read_text(encoding="utf-8")
        cls.backend_admin = (ROOT / "backend/app/routes/admin.py").read_text(encoding="utf-8")

    def test_role_home_paths_and_verified_profile_are_centralized(self):
        self.assertIn('student: "/student/"', self.auth_client)
        self.assertIn('organizer: "/organizer/"', self.auth_client)
        self.assertIn('admin: "/admin/"', self.auth_client)
        self.assertIn('callApi("/api/auth/me", session)', self.auth_client)
        self.assertNotIn("localStorage", self.auth_client)

    def test_public_entries_redirect_authenticated_users_and_logout_clears_session(self):
        self.assertIn("isPublicEntryPage", self.auth_client)
        self.assertIn("window.location.replace(consumeAuthorizedReturnTo(profile.role) || destination)", self.auth_client)
        self.assertIn("sessionStorage.removeItem(eventSphereReturnToKey)", self.auth_client)
        self.assertIn('window.location.replace("/")', self.auth_client)

    def test_deep_links_are_saved_with_an_expected_role(self):
        self.assertIn("saveReturnTo(requiredRole)", self.auth_client)
        self.assertIn("allowedRoles.includes(role)", self.auth_client)
        self.assertIn('redirectToLogin("student")', (FRONTEND / "assets/js/event-pass.js").read_text(encoding="utf-8"))
        self.assertIn('redirectToLogin(["organizer", "admin"])', (FRONTEND / "organizer/events/manage.js").read_text(encoding="utf-8"))
        self.assertIn("redirectToLogin(scannerRole())", (FRONTEND / "assets/js/attendance-scanner.js").read_text(encoding="utf-8"))

    def test_cross_role_dashboard_access_redirects_to_verified_role_home(self):
        self.assertIn("window.location.replace(roleHomePath(profileBody.profile.role))", self.dashboard)
        self.assertIn("window.location.replace(roleHomePath(identity.profile.role))", self.protected_dashboard)

    def test_backend_role_and_master_admin_protection_remain_in_place(self):
        self.assertIn('@require_role("student")', self.backend_dashboard)
        self.assertIn('@require_role("organizer")', self.backend_dashboard)
        self.assertIn('@require_role("admin")', self.backend_dashboard)
        self.assertIn("@require_master_admin", self.backend_admin)
        self.assertIn("profile.is_master_admin !== true", self.dashboard)

    def test_dashboard_and_logo_home_links_exist_for_each_role(self):
        for role in ("student", "organizer", "admin"):
            page = (FRONTEND / "dashboard" / role / "index.html").read_text(encoding="utf-8")
            self.assertIn("EventSphere", page)
            self.assertIn("Dashboard", page)


if __name__ == "__main__":
    unittest.main()
