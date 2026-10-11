import sys
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import create_app  # noqa: E402
from app.db import get_connection  # noqa: E402
from integration_support import require_integration_database, resolve_profile_id  # noqa: E402


STUDENT_ONE = {"id": "00000000-0000-0000-0000-000000000001", "email": "aarav.student@example.test"}
STUDENT_TWO = {"id": "00000000-0000-0000-0000-000000000002", "email": "mira.student@example.test"}
ORGANIZER = {"id": resolve_profile_id("rohan.organizer@example.test", "00000000-0000-0000-0000-000000000003"), "email": "organizer@example.test"}


def profile(user, role="student"):
    return {"id": user["id"], "full_name": "Test User", "email": user["email"], "role": role}


class TeamRegistrationApiTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        require_integration_database()
        app = create_app()
        app.config.update(TESTING=True)
        cls.client = app.test_client()

    def setUp(self):
        self.event_id = uuid.uuid4()
        deadline = datetime.now(timezone.utc) + timedelta(days=30)
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """insert into events(id,title,description,category_id,organizer_id,venue_id,event_date,start_time,end_time,capacity,registration_deadline,status,participation_mode,min_team_size,max_team_size)
                       values(%s,%s,'team test',%s,%s,%s,current_date + 30,'10:00','12:00',3,%s,'published','both',2,3)""",
                    (self.event_id, f"Team test {self.event_id}", "10000000-0000-0000-0000-000000000001", ORGANIZER["id"], "20000000-0000-0000-0000-000000000004", deadline),
                )

    def tearDown(self):
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("delete from registrations where event_id=%s", (self.event_id,))
                cursor.execute("delete from teams where event_id=%s", (self.event_id,))
                cursor.execute("delete from events where id=%s", (self.event_id,))

    def _auth(self, user):
        return patch.multiple("app.routes.auth", verify_access_token=lambda token: user, _load_profile=lambda user_id: profile(user))

    def test_team_registration_persists_members_and_cancels(self):
        payload = {"participation_type": "team", "team": {"name": "Blue Orbit", "members": [{"full_name": "Student Two", "email": STUDENT_TWO["email"]}]}}
        with self._auth(STUDENT_ONE):
            created = self.client.post(f"/api/events/{self.event_id}/register", json=payload, headers={"Authorization": "Bearer student-one"})
            self.assertEqual(created.status_code, 201)
            self.assertEqual(created.get_json()["data"]["participation_type"], "team")
            self.assertEqual(self.client.delete(f"/api/events/{self.event_id}/register", headers={"Authorization": "Bearer student-one"}).status_code, 200)
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("select count(*) from team_members tm join teams t on t.id=tm.team_id where t.event_id=%s", (self.event_id,))
                self.assertEqual(cursor.fetchone()[0], 2)

    def test_invalid_team_size_and_duplicate_member_are_rejected(self):
        with self._auth(STUDENT_ONE):
            too_small = self.client.post(f"/api/events/{self.event_id}/register", json={"participation_type": "team", "team": {"name": "Too Small", "members": []}}, headers={"Authorization": "Bearer student-one"})
            duplicate = self.client.post(f"/api/events/{self.event_id}/register", json={"participation_type": "team", "team": {"name": "Duplicate", "members": [{"full_name": "A", "email": STUDENT_TWO["email"]}, {"full_name": "B", "email": STUDENT_TWO["email"]}]}}, headers={"Authorization": "Bearer student-one"})
        self.assertEqual(too_small.status_code, 422)
        self.assertEqual(duplicate.status_code, 422)

    def test_individual_mode_is_rejected_when_event_only_accepts_teams(self):
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("update events set participation_mode='team', min_team_size=2, max_team_size=3 where id=%s", (self.event_id,))
        with self._auth(STUDENT_ONE):
            response = self.client.post(f"/api/events/{self.event_id}/register", json={"participation_type": "individual"}, headers={"Authorization": "Bearer student-one"})
        self.assertEqual(response.status_code, 409)

    def test_capacity_counts_team_registrations_transactionally(self):
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("update events set capacity=1 where id=%s", (self.event_id,))
        payload = {"participation_type": "team", "team": {"name": "First Team", "members": [{"full_name": "Guest Member", "email": "guest.member@example.test"}]}}
        with self._auth(STUDENT_ONE):
            self.assertEqual(self.client.post(f"/api/events/{self.event_id}/register", json=payload, headers={"Authorization": "Bearer student-one"}).status_code, 201)
        with self._auth(STUDENT_TWO):
            response = self.client.post(f"/api/events/{self.event_id}/register", json={"participation_type": "team", "team": {"name": "Second Team", "members": [{"full_name": "Another Guest", "email": "another.guest@example.test"}]}}, headers={"Authorization": "Bearer student-two"})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["error"]["code"], "EVENT_FULL")


if __name__ == "__main__":
    unittest.main()
