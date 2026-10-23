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

import psycopg


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "tests"))

from app import create_app  # noqa: E402
from app.db import get_connection  # noqa: E402
from app.services import event_service  # noqa: E402
from integration_support import require_integration_database, resolve_profile_id  # type: ignore  # noqa: E402  # pyright: ignore[reportMissingImports]


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
        self.assertIn("_, event_status, started_at, started_by, ended_at = row", source)
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


LIFECYCLE_EVENT_ID = "00000000-0000-0000-0000-0000000000aa"
LIFECYCLE_ACTOR_ID = "00000000-0000-0000-0000-0000000000ab"


class RecordingCursor:
    """Cursor stub that records SQL so a test can prove nothing was written."""

    def __init__(self, row):
        self.row = row
        self.statements = []

    def execute(self, statement, params=None):
        self.statements.append(" ".join(statement.split()))

    def fetchone(self):
        return self.row

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def wrote(self, needle):
        return any(needle in statement.lower() for statement in self.statements)

    def mutated(self):
        """True if any statement writes. Ignores the locking `select ... for update`."""

        return any(
            statement.split(" ", 1)[0] in {"update", "insert", "delete"}
            for statement in self.statements
        )


class StubConnection:
    def __init__(self, row):
        self.cursor_instance = RecordingCursor(row)

    def cursor(self):
        return self.cursor_instance

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


class ConstraintCursor(RecordingCursor):
    """Stands in for PostgreSQL enforcing events_lifecycle_order_check.

    A real INSERT/UPDATE that breaks the CHECK raises psycopg.errors.CheckViolation,
    which is a DatabaseError and is therefore swallowed by the route's error branch
    as a generic HTTP 500. Reproducing that here is what makes the API test below a
    genuine "no longer a 500" regression test rather than a status-code assertion.
    """

    def execute(self, statement, params=None):
        if " ".join(statement.split()).lower().startswith("update"):
            raise psycopg.errors.CheckViolation(
                'new row for relation "events" violates check constraint '
                '"events_lifecycle_order_check"'
            )
        super().execute(statement, params)


class SingleCursorConnection:
    """Connection stub built around one prepared cursor instance."""

    def __init__(self, cursor):
        self.cursor_instance = cursor

    def cursor(self):
        return self.cursor_instance

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


def lifecycle_row(status, started_at, ended_at, started_by=None, ended_by=None):
    """Row shape of the select in end_event: id, status, started_at, started_by, ended_at, ended_by."""

    return (
        uuid.UUID(LIFECYCLE_EVENT_ID),
        status,
        started_at,
        started_by,
        ended_at,
        ended_by,
    )


class EndEventServiceTestCase(unittest.TestCase):
    """Database-free coverage of the manual End path in event_service.

    Regression for the audit finding F1: a published event that was never started
    used to reach the events_lifecycle_order_check constraint, so PostgreSQL raised
    a CheckViolation and the route answered HTTP 500.
    """

    def setUp(self):
        self.now = datetime.now(timezone.utc)
        patcher = patch("app.services.event_service.include_lifecycle_columns", return_value=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _call(self, row):
        connection = StubConnection(row)
        patcher = patch("app.services.event_service.get_connection", return_value=connection)
        patcher.start()
        self.addCleanup(patcher.stop)
        result, failure = None, None
        try:
            result = event_service.end_event(LIFECYCLE_EVENT_ID, LIFECYCLE_ACTOR_ID)
        except ValueError as exc:
            failure = exc
        return result, failure, connection.cursor_instance

    def test_schema_not_ready_raises_error(self):
        with patch("app.services.event_service.include_lifecycle_columns", return_value=False):
            with self.assertRaises(event_service.SchemaNotReadyError):
                event_service.end_event(LIFECYCLE_EVENT_ID, LIFECYCLE_ACTOR_ID)

    def test_never_started_event_is_refused_without_writing(self):
        result, failure, cursor = self._call(lifecycle_row("published", None, None))

        self.assertIsNone(result)
        self.assertIsInstance(failure, ValueError)
        self.assertIn("started", str(failure).lower())
        self.assertFalse(cursor.mutated(), "end_event must not UPDATE a never-started event")
        self.assertFalse(cursor.wrote("event_lifecycle_audit"), "no audit row for a refused end")

    def test_started_event_is_ended_and_audited(self):
        started = self.now - timedelta(minutes=5)
        result, failure, cursor = self._call(
            lifecycle_row("published", started, None, started_by=uuid.UUID(LIFECYCLE_ACTOR_ID))
        )

        self.assertIsNone(failure)
        assert result is not None
        self.assertEqual(result["operational_state"], "ended")
        self.assertFalse(result["already_ended"])
        self.assertTrue(cursor.mutated())
        self.assertTrue(cursor.wrote("update events set ended_at"))
        self.assertTrue(cursor.wrote("event_lifecycle_audit"))

    def test_already_ended_event_is_idempotent_and_writes_nothing(self):
        started = self.now - timedelta(hours=1)
        result, failure, cursor = self._call(lifecycle_row("published", started, self.now))

        self.assertIsNone(failure)
        assert result is not None
        self.assertTrue(result["already_ended"])
        self.assertEqual(result["operational_state"], "ended")
        self.assertFalse(cursor.mutated(), "a repeated end must not rewrite the row")
        self.assertFalse(cursor.wrote("event_lifecycle_audit"))

    def test_unpublished_event_is_refused(self):
        result, failure, cursor = self._call(lifecycle_row("draft", None, None))

        self.assertIsNone(result)
        self.assertIsInstance(failure, ValueError)
        self.assertIn("published", str(failure).lower())
        self.assertFalse(cursor.mutated())

    def test_missing_event_returns_none(self):
        result, failure, _ = self._call(None)

        self.assertIsNone(result)
        self.assertIsNone(failure)


class EndEventApiTestCase(unittest.TestCase):
    """Database-free API coverage: POST /api/events/<id>/end must answer with a
    controlled client error and must never reach a database write for an event
    that was never started."""

    def setUp(self):
        app = create_app()
        app.config.update(TESTING=True)
        self.client = app.test_client()

    def _published_event(self, operational_state):
        # Mirrors serialize_event: started_at/ended_at are popped, and
        # operational_state is only attached to published events.
        return {
            "id": LIFECYCLE_EVENT_ID,
            "title": "Lifecycle Test Event",
            "status": "published",
            "operational_state": operational_state,
            "organizer": {"id": ORGANIZER["id"], "name": "Rohan Iyer"},
        }

    def _post_end(self, operational_state, confirm=True, service_result=None):
        with patch("app.routes.auth.verify_access_token", return_value=ORGANIZER), patch(
            "app.routes.auth._load_profile", return_value=profile(ORGANIZER, "organizer")
        ), patch.object(
            event_service, "get_event", return_value=self._published_event(operational_state)
        ), patch.object(
            event_service, "end_event", return_value=service_result
        ) as end_event_mock:
            response = self.client.post(
                f"/api/events/{LIFECYCLE_EVENT_ID}/end",
                json={"confirm": confirm},
                headers={"Authorization": "Bearer test-token"},
            )
        return response, end_event_mock

    def test_published_but_never_started_is_a_client_error_not_a_500(self):
        response, end_event_mock = self._post_end("scheduled")

        self.assertLess(response.status_code, 500, response.get_data(as_text=True))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["error"]["code"], "INVALID_STATE")
        end_event_mock.assert_not_called()

    def test_running_event_still_reaches_the_service(self):
        response, end_event_mock = self._post_end(
            "running",
            service_result={"id": LIFECYCLE_EVENT_ID, "operational_state": "ended", "already_ended": False},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json()["data"]["already_ended"])
        end_event_mock.assert_called_once()

    def test_already_ended_event_remains_idempotent(self):
        response, end_event_mock = self._post_end(
            "ended",
            service_result={"id": LIFECYCLE_EVENT_ID, "operational_state": "ended", "already_ended": True},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["data"]["already_ended"])
        end_event_mock.assert_called_once()

    def test_never_started_end_never_reaches_the_lifecycle_check(self):
        """End-to-end through the real service with the CHECK enforced.

        Without the guard this UPDATE raises CheckViolation and the route answers
        500; the guard must keep the request at a client error and off the table.
        """

        self.assertTrue(issubclass(psycopg.errors.CheckViolation, psycopg.DatabaseError))
        cursor = ConstraintCursor(lifecycle_row("published", None, None))
        with patch("app.routes.auth.verify_access_token", return_value=ORGANIZER), patch(
            "app.routes.auth._load_profile", return_value=profile(ORGANIZER, "organizer")
        ), patch.object(
            event_service, "get_event", return_value=self._published_event("scheduled")
        ), patch(
            "app.services.event_service.get_connection", return_value=SingleCursorConnection(cursor)
        ):
            response = self.client.post(
                f"/api/events/{LIFECYCLE_EVENT_ID}/end",
                json={"confirm": True},
                headers={"Authorization": "Bearer test-token"},
            )

        self.assertNotEqual(response.status_code, 500, response.get_data(as_text=True))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["error"]["code"], "INVALID_STATE")
        self.assertFalse(cursor.mutated(), "the guard must stop the write before the CHECK")

    def test_missing_confirmation_is_rejected_before_any_lookup(self):
        with patch("app.routes.auth.verify_access_token", return_value=ORGANIZER), patch(
            "app.routes.auth._load_profile", return_value=profile(ORGANIZER, "organizer")
        ), patch.object(event_service, "get_event") as get_event_mock:
            response = self.client.post(
                f"/api/events/{LIFECYCLE_EVENT_ID}/end",
                json={},
                headers={"Authorization": "Bearer test-token"},
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"]["code"], "CONFIRMATION_REQUIRED")
        get_event_mock.assert_not_called()


def lifecycle_start_row(status, started_at, ended_at, started_by=None):
    return (
        uuid.UUID(LIFECYCLE_EVENT_ID),
        status,
        started_at,
        started_by,
        ended_at,
    )


class StartEventServiceTestCase(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        patcher = patch("app.services.event_service.include_lifecycle_columns", return_value=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _call(self, row):
        connection = StubConnection(row)
        patcher = patch("app.services.event_service.get_connection", return_value=connection)
        patcher.start()
        self.addCleanup(patcher.stop)
        result, failure = None, None
        try:
            result = event_service.start_event(LIFECYCLE_EVENT_ID, LIFECYCLE_ACTOR_ID)
        except ValueError as exc:
            failure = exc
        return result, failure, connection.cursor_instance

    def test_schema_not_ready_raises_error(self):
        with patch("app.services.event_service.include_lifecycle_columns", return_value=False):
            with self.assertRaises(event_service.SchemaNotReadyError):
                event_service.start_event(LIFECYCLE_EVENT_ID, LIFECYCLE_ACTOR_ID)

    def test_scheduled_event_is_started_and_audited(self):
        result, failure, cursor = self._call(lifecycle_start_row("published", None, None))
        self.assertIsNone(failure)
        assert result is not None
        self.assertEqual(result["operational_state"], "running")
        self.assertFalse(result["already_started"])
        self.assertTrue(cursor.mutated())
        self.assertTrue(cursor.wrote("update events set started_at"))
        self.assertTrue(cursor.wrote("event_lifecycle_audit"))

    def test_already_started_event_is_idempotent(self):
        started = self.now - timedelta(minutes=10)
        result, failure, cursor = self._call(lifecycle_start_row("published", started, None, started_by=uuid.UUID(LIFECYCLE_ACTOR_ID)))
        self.assertIsNone(failure)
        assert result is not None
        self.assertTrue(result["already_started"])
        self.assertEqual(result["operational_state"], "running")
        self.assertFalse(cursor.mutated())

    def test_already_ended_event_refuses_start_without_writing(self):
        started = self.now - timedelta(hours=1)
        ended = self.now - timedelta(minutes=5)
        result, failure, cursor = self._call(lifecycle_start_row("published", started, ended))
        self.assertIsNone(result)
        self.assertIsInstance(failure, ValueError)
        self.assertIn("ended", str(failure).lower())
        self.assertFalse(cursor.mutated())

    def test_draft_event_refuses_start(self):
        result, failure, cursor = self._call(lifecycle_start_row("draft", None, None))
        self.assertIsNone(result)
        self.assertIsInstance(failure, ValueError)
        self.assertIn("published", str(failure).lower())
        self.assertFalse(cursor.mutated())


class StartEventApiTestCase(unittest.TestCase):
    def setUp(self):
        app = create_app()
        app.config.update(TESTING=True)
        self.client = app.test_client()

    def _published_event(self, operational_state):
        return {
            "id": LIFECYCLE_EVENT_ID,
            "title": "Lifecycle Test Event",
            "status": "published",
            "operational_state": operational_state,
            "organizer": {"id": ORGANIZER["id"], "name": "Rohan Iyer"},
        }

    def _post_start(self, operational_state, service_result=None):
        with patch("app.routes.auth.verify_access_token", return_value=ORGANIZER), patch(
            "app.routes.auth._load_profile", return_value=profile(ORGANIZER, "organizer")
        ), patch.object(
            event_service, "get_event", return_value=self._published_event(operational_state)
        ), patch.object(
            event_service, "start_event", return_value=service_result
        ) as start_event_mock:
            response = self.client.post(
                f"/api/events/{LIFECYCLE_EVENT_ID}/start",
                headers={"Authorization": "Bearer test-token"},
            )
        return response, start_event_mock

    def test_already_ended_event_start_is_client_error(self):
        response, start_mock = self._post_start("ended")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["error"]["code"], "INVALID_STATE")
        start_mock.assert_not_called()

    def test_scheduled_event_start_succeeds(self):
        response, start_mock = self._post_start(
            "scheduled",
            service_result={"id": LIFECYCLE_EVENT_ID, "operational_state": "running", "already_started": False},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json()["data"]["already_started"])
        start_mock.assert_called_once()

    def test_unauthorized_organizer_start_refused(self):
        unowned_event = {
            "id": LIFECYCLE_EVENT_ID,
            "title": "Other Organizer Event",
            "status": "published",
            "operational_state": "scheduled",
            "organizer": {"id": OTHER_ORGANIZER["id"], "name": "Other Organizer"},
        }
        with patch("app.routes.auth.verify_access_token", return_value=ORGANIZER), patch(
            "app.routes.auth._load_profile", return_value=profile(ORGANIZER, "organizer")
        ), patch.object(
            event_service, "get_event", return_value=unowned_event
        ), patch.object(
            event_service, "start_event"
        ) as start_mock:
            response = self.client.post(
                f"/api/events/{LIFECYCLE_EVENT_ID}/start",
                headers={"Authorization": "Bearer test-token"},
            )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"]["code"], "FORBIDDEN")
        start_mock.assert_not_called()

    def test_start_event_before_scheduled_time_succeeds(self):
        future_event = {
            "id": LIFECYCLE_EVENT_ID,
            "title": "Future Event",
            "status": "published",
            "operational_state": "scheduled",
            "event_date": "2099-12-31",
            "start_time": "18:00:00",
            "organizer": {"id": ORGANIZER["id"], "name": "Rohan Iyer"},
        }
        with patch("app.routes.auth.verify_access_token", return_value=ORGANIZER), patch(
            "app.routes.auth._load_profile", return_value=profile(ORGANIZER, "organizer")
        ), patch.object(
            event_service, "get_event", return_value=future_event
        ), patch.object(
            event_service, "start_event", return_value={"id": LIFECYCLE_EVENT_ID, "operational_state": "running", "already_started": False}
        ) as start_mock:
            response = self.client.post(
                f"/api/events/{LIFECYCLE_EVENT_ID}/start",
                headers={"Authorization": "Bearer test-token"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["data"]["operational_state"], "running")
        start_mock.assert_called_once()

    def test_start_event_when_lifecycle_columns_missing_returns_schema_outdated(self):
        with patch("app.routes.auth.verify_access_token", return_value=ORGANIZER), patch(
            "app.routes.auth._load_profile", return_value=profile(ORGANIZER, "organizer")
        ), patch.object(
            event_service, "get_event", return_value=self._published_event("scheduled")
        ), patch.object(
            event_service, "include_lifecycle_columns", return_value=False
        ):
            response = self.client.post(
                f"/api/events/{LIFECYCLE_EVENT_ID}/start",
                headers={"Authorization": "Bearer test-token"},
            )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["error"]["code"], "SCHEMA_OUTDATED")
        self.assertIn("20261012100000_manual_event_lifecycle.sql", response.get_json()["error"]["message"])

    def test_end_event_when_lifecycle_columns_missing_returns_schema_outdated(self):
        with patch("app.routes.auth.verify_access_token", return_value=ORGANIZER), patch(
            "app.routes.auth._load_profile", return_value=profile(ORGANIZER, "organizer")
        ), patch.object(
            event_service, "get_event", return_value=self._published_event("running")
        ), patch.object(
            event_service, "include_lifecycle_columns", return_value=False
        ):
            response = self.client.post(
                f"/api/events/{LIFECYCLE_EVENT_ID}/end",
                json={"confirm": True},
                headers={"Authorization": "Bearer test-token"},
            )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["error"]["code"], "SCHEMA_OUTDATED")




class EventListingScopeTestCase(unittest.TestCase):
    def setUp(self):
        app = create_app()
        app.config.update(TESTING=True)
        self.client = app.test_client()

    def test_public_listing_hides_draft_and_pending(self):
        with patch.object(event_service, "list_events", return_value=([], 0)) as list_mock:
            self.client.get("/api/events")
        args, _ = list_mock.call_args
        filters, role, user_id = args
        self.assertIsNone(role)
        self.assertIsNone(user_id)

    def test_organizer_listing_is_scoped_to_user_id(self):
        with patch("app.routes.events.verify_access_token", return_value=ORGANIZER), patch(
            "app.routes.events._load_profile", return_value=profile(ORGANIZER, "organizer")
        ), patch.object(event_service, "list_events", return_value=([], 0)) as list_mock:
            response = self.client.get("/api/events", headers={"Authorization": "Bearer test-token"})
        self.assertEqual(response.status_code, 200)
        args, _ = list_mock.call_args
        filters, role, user_id = args
        self.assertEqual(role, "organizer")
        self.assertEqual(user_id, ORGANIZER["id"])



if __name__ == "__main__":
    unittest.main()
