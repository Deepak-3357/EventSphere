"""Regression tests for the code -> database schema contract.

The production outage these tests guard against: the backend started selecting
``events.started_at``/``events.ended_at`` in the shared event list query while
``supabase/migrations/20261012100000_manual_event_lifecycle.sql`` had not been
applied to the Supabase project. PostgreSQL raised ``UndefinedColumn`` (42703),
``list_events`` caught it as ``DatabaseError``, and ``GET /api/events`` -- the
single endpoint behind both the organizer and the public event pages --
returned ``500 DATABASE_ERROR`` for every role.

Two gaps made that possible and are closed here:

* nothing tied backend SQL to the migration set, so code could reference an
  object no migration creates;
* every database-backed test is opt-in and skipped by default, so an unapplied
  migration was invisible to CI.

All tests in this file are database-free.
"""

import ast
import re
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import psycopg


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import create_app  # noqa: E402
from app import schema_contract  # noqa: E402
from app.routes import health as health_routes  # noqa: E402
from app.services import (  # noqa: E402
    dashboard_service,
    event_service,
    od_letter_service,
    registration_service,
)


MIGRATIONS_DIR = ROOT / "supabase" / "migrations"

# Modules that alias ``public.events`` as ``e`` in their SQL.
EVENT_QUERY_MODULES = (
    event_service,
    dashboard_service,
    registration_service,
    od_letter_service,
)

TABLE_CONSTRAINT_KEYWORDS = {
    "constraint", "primary", "unique", "check", "foreign", "exclude", "like", "table",
}

LIFECYCLE_COLUMNS = ("started_at", "started_by", "ended_at", "ended_by")


def string_literals(module):
    """Return every string literal in a module, so SQL is scanned and code is not."""

    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]


def events_alias_columns(module):
    """Return the ``e.<column>`` references a module makes in its SQL."""

    return {
        match.group(1).lower()
        for text in string_literals(module)
        for match in re.finditer(r"\be\.([A-Za-z_][A-Za-z0-9_]*)", text)
    }


def _create_table_columns(sql, table):
    pattern = re.compile(
        r"create\s+table\s+(?:if\s+not\s+exists\s+)?(?:public\.)?" + re.escape(table) + r"\s*\((.*?)^\s*\)\s*;",
        re.IGNORECASE | re.DOTALL | re.MULTILINE,
    )
    columns = set()
    for body in pattern.findall(sql):
        for line in body.splitlines():
            line = line.split("--", 1)[0].strip()
            match = re.match(r"([A-Za-z_][A-Za-z0-9_]*)\s+", line)
            if match and match.group(1).lower() not in TABLE_CONSTRAINT_KEYWORDS:
                columns.add(match.group(1).lower())
    return columns


def _altered_table_columns(sql, table):
    pattern = re.compile(
        r"alter\s+table\s+(?:if\s+exists\s+)?(?:public\.)?" + re.escape(table) + r"\b(.*?);",
        re.IGNORECASE | re.DOTALL,
    )
    columns = set()
    for body in pattern.findall(sql):
        columns.update(
            column.lower()
            for column in re.findall(
                r"add\s+column\s+(?:if\s+not\s+exists\s+)?([A-Za-z_][A-Za-z0-9_]*)", body, re.IGNORECASE
            )
        )
    return columns


def migration_schema():
    """Return ``{table: {column, ...}}`` as declared by the checked-in migrations."""

    sql = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(MIGRATIONS_DIR.glob("*.sql"))
    )
    declared = {}
    for table in schema_contract.REQUIRED_TABLES:
        columns = _create_table_columns(sql, table) | _altered_table_columns(sql, table)
        if columns:
            declared[table] = columns
    return declared


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, *args, **kwargs):
        return None

    def fetchall(self):
        return list(self.rows)

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


class FakeConnection:
    def __init__(self, rows):
        self.rows = rows

    def cursor(self):
        return FakeCursor(self.rows)

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


def current_schema_rows():
    """information_schema rows for a database that matches the contract."""

    rows = []
    for table in schema_contract.REQUIRED_TABLES:
        columns = schema_contract.REQUIRED_COLUMNS.get(table) or ("id",)
        rows.extend((table, column) for column in columns)
    return rows


def production_schema_rows():
    """information_schema rows for production when the lifecycle migration is missing."""

    rows = []
    for table, column in current_schema_rows():
        if table == "event_lifecycle_audit":
            continue
        if table == "events" and column in LIFECYCLE_COLUMNS:
            continue
        rows.append((table, column))
    return rows


class SchemaContractTestCase(unittest.TestCase):
    def test_event_queries_only_reference_contract_columns(self):
        referenced = set()
        for module in EVENT_QUERY_MODULES:
            referenced |= events_alias_columns(module)

        self.assertTrue(referenced, "the event SQL scan found no e.<column> references")
        self.assertEqual(
            referenced - set(schema_contract.REQUIRED_COLUMNS["events"]),
            set(),
            "add new event columns to schema_contract.REQUIRED_COLUMNS",
        )

    def test_manual_lifecycle_write_columns_are_declared(self):
        declared = set(schema_contract.REQUIRED_COLUMNS["events"])
        for column in LIFECYCLE_COLUMNS:
            self.assertIn(column, declared)

    def test_every_required_object_is_created_by_a_migration(self):
        declared = migration_schema()

        for table in schema_contract.REQUIRED_TABLES:
            self.assertIn(
                table,
                declared,
                f"no migration creates public.{table}",
            )

        for table, columns in schema_contract.REQUIRED_COLUMNS.items():
            missing = sorted(set(columns) - declared[table])
            self.assertEqual(missing, [], f"no migration declares {table}.{missing}")

    def test_lifecycle_migration_declares_the_lifecycle_columns(self):
        declared = migration_schema()["events"]
        for column in LIFECYCLE_COLUMNS:
            self.assertIn(column, declared)


class SchemaReadinessTestCase(unittest.TestCase):
    def test_ready_when_the_database_matches_the_contract(self):
        report = schema_contract.schema_status(connection_factory=lambda: FakeConnection(current_schema_rows()))

        self.assertTrue(report["available"])
        self.assertTrue(report["ready"])
        self.assertEqual(report["missing"], {"tables": [], "columns": []})

    def test_not_ready_when_the_lifecycle_migration_is_unapplied(self):
        """The exact production state that broke both event pages."""

        report = schema_contract.schema_status(
            connection_factory=lambda: FakeConnection(production_schema_rows())
        )

        self.assertTrue(report["available"])
        self.assertFalse(report["ready"])
        self.assertEqual(report["missing"]["tables"], ["event_lifecycle_audit"])
        self.assertEqual(
            sorted(report["missing"]["columns"]),
            sorted(f"events.{column}" for column in LIFECYCLE_COLUMNS),
        )

    def test_unreachable_database_is_reported_as_unavailable(self):
        def factory():
            raise psycopg.OperationalError("host=example.invalid password=not-a-real-password")

        report = schema_contract.schema_status(connection_factory=factory)

        self.assertFalse(report["available"])
        self.assertFalse(report["ready"])
        self.assertNotIn("not-a-real-password", repr(report))


class SchemaHealthEndpointTestCase(unittest.TestCase):
    def setUp(self):
        app = create_app()
        app.config.update(TESTING=True)
        self.client = app.test_client()
        health_routes.reset_schema_cache()

    def tearDown(self):
        health_routes.reset_schema_cache()

    def test_liveness_response_is_unchanged(self):
        response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"status": "ok", "service": "EventSphere API"})

    def test_readiness_reports_current_schema(self):
        with patch.object(
            schema_contract,
            "schema_status",
            return_value={"available": True, "ready": True, "missing": {"tables": [], "columns": []}},
        ):
            response = self.client.get("/api/health/schema")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["schema"], "current")

    def test_readiness_reports_the_pending_migration(self):
        with patch.object(
            schema_contract,
            "schema_status",
            return_value={
                "available": True,
                "ready": False,
                "missing": {
                    "tables": ["event_lifecycle_audit"],
                    "columns": ["events.started_at", "events.ended_at"],
                },
            },
        ):
            response = self.client.get("/api/health/schema")

        self.assertEqual(response.status_code, 503)
        body = response.get_json()
        self.assertEqual(body["schema"], "outdated")
        self.assertEqual(body["missing"]["tables"], ["event_lifecycle_audit"])
        self.assertEqual(body["missing"]["columns"], ["events.started_at", "events.ended_at"])

    def test_readiness_does_not_leak_connection_detail(self):
        with patch.object(
            schema_contract,
            "schema_status",
            return_value={"available": False, "ready": False, "missing": {"tables": [], "columns": []}},
        ):
            response = self.client.get("/api/health/schema")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["schema"], "unavailable")


if __name__ == "__main__":
    unittest.main()
