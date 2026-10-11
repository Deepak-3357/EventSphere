import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import create_app  # noqa: E402


STUDENT = {"id": "00000000-0000-0000-0000-000000000001", "email": "student@example.test"}
ADMIN = {"id": "00000000-0000-0000-0000-000000000005", "email": "admin@example.test"}


def profile(user, role, master=False):
    return {"id": user["id"], "full_name": role.title(), "email": user["email"], "role": role, "is_master_admin": master}


class MasterAdminApiTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app = create_app(); app.config.update(TESTING=True); cls.client = app.test_client()

    def auth(self, user, role, master=False):
        return patch.multiple("app.routes.auth", verify_access_token=lambda token: user, _load_profile=lambda user_id: profile(user, role, master))

    def test_unauthenticated_and_non_master_users_are_denied(self):
        self.assertEqual(self.client.get("/api/admin/users").status_code, 401)
        with self.auth(STUDENT, "student"):
            self.assertEqual(self.client.get("/api/admin/users", headers={"Authorization": "Bearer x"}).status_code, 403)
        with self.auth(ADMIN, "admin"):
            self.assertEqual(self.client.get("/api/admin/users", headers={"Authorization": "Bearer x"}).status_code, 403)

    def test_master_can_list_and_create_only_privileged_accounts(self):
        with patch("app.routes.admin.admin_service.list_profiles", return_value=[]), patch("app.routes.admin.admin_service.create_privileged_user", return_value={"id": "new", "role": "organizer"}) as create:
            with self.auth(ADMIN, "admin", True):
                headers = {"Authorization": "Bearer x"}
                listed = self.client.get("/api/admin/users?role=organizer", headers=headers)
                created = self.client.post("/api/admin/users", json={"full_name": "Organizer", "email": "organizer2@example.test", "role": "organizer", "password": "SafePass123!"}, headers=headers)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(created.status_code, 201)
        create.assert_called_once()

    def test_master_flag_is_not_accepted_from_request_body(self):
        with patch("app.routes.admin.admin_service.create_privileged_user", return_value={"id": "new", "role": "admin", "is_master_admin": False}) as create:
            with self.auth(ADMIN, "admin", True):
                response = self.client.post("/api/admin/users", json={"full_name": "Admin", "email": "ordinary@example.test", "role": "admin", "is_master_admin": True, "password": "SafePass123!"}, headers={"Authorization": "Bearer x"})
        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.get_json()["data"]["is_master_admin"])
        self.assertFalse(create.call_args.args[0].get("is_master_admin", False))


if __name__ == "__main__":
    unittest.main()
