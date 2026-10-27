"""Static contract for the database objects the API depends on.

The Flask backend and the Supabase schema live in the same repository but are
deployed by two different pipelines: Render ships ``backend/``, while
``supabase/migrations/*.sql`` has to be applied to the database separately.
When the two drift apart the API starts issuing SQL the database cannot run,
and every route that touches the changed object collapses into the same
generic 500. That is what took out both event lists: the backend began
selecting ``events.started_at``/``events.ended_at`` in the shared list query
while the manual lifecycle migration had not been applied yet.

Keeping the dependency in one auditable place lets a mismatch be reported as
what it is -- a deployment fault -- instead of a broken page. See
``GET /api/health/schema``.
"""

import time

from psycopg import Error as PsycopgError

SCHEMA_NAME = "public"

# Every table the API reads or writes. A table missing from the database means
# the schema is behind the deployed code.
REQUIRED_TABLES = (
    "profiles",
    "categories",
    "venues",
    "events",
    "registrations",
    "notifications",
    "event_faqs",
    "event_lifecycle_audit",
    "od_letters",
    "teams",
    "team_members",
    "venue_bookings",
)

# Columns on ``public.events`` referenced by the event, dashboard,
# registration, and OD-letter services. ``started_at``/``ended_at`` are part of
# the shared event SELECT, so the catalog cannot load for any role until the
# manual lifecycle migration is applied; ``started_by``/``ended_by`` are
# written by the manual start/end paths.
#
# ``tests/test_schema_contract.py`` derives this list from the SQL in those
# services and fails if a query starts using a column that is not declared
# here, so the contract cannot silently fall behind the code.
REQUIRED_COLUMNS = {
    "venues": (
        "id",
        "name",
        "location",
        "capacity",
        "created_at",
        "is_active",
    ),
    "events": (
        "id",
        "title",
        "description",
        "category_id",
        "organizer_id",
        "venue_id",
        "event_date",
        "start_time",
        "end_time",
        "capacity",
        "registration_deadline",
        "status",
        "image_url",
        "participation_mode",
        "min_team_size",
        "max_team_size",
        "eligibility",
        "registration_instructions",
        "facilities",
        "created_at",
        "updated_at",
        "started_at",
        "started_by",
        "ended_at",
        "ended_by",
    ),
    "venue_bookings": (
        "id",
        "venue_id",
        "requester_id",
        "event_id",
        "title",
        "start_at",
        "end_at",
        "status",
        "created_at",
        "updated_at",
    ),
}


def missing_schema_objects(cursor):
    """Return the required objects the connected database does not have.

    ``information_schema.columns`` is enough for both checks: a table that
    exists always has at least one column, so an absent table yields no rows.
    """

    cursor.execute(
        "select table_name, column_name from information_schema.columns where table_schema = %s",
        (SCHEMA_NAME,),
    )
    present = {}
    for table, column in cursor.fetchall():
        present.setdefault(table, set()).add(column)

    return {
        "tables": [table for table in REQUIRED_TABLES if table not in present],
        "columns": [
            f"{table}.{column}"
            for table, columns in REQUIRED_COLUMNS.items()
            for column in columns
            if table in present and column not in present[table]
        ],
    }


def schema_status(connection_factory=None):
    """Report whether the database schema matches this deployment.

    Never raises and never leaks connection detail: a database the API cannot
    reach is reported as unavailable, which is also "not ready".
    """

    from app.db import get_connection

    factory = connection_factory or get_connection
    try:
        with factory() as connection:
            with connection.cursor() as cursor:
                missing = missing_schema_objects(cursor)
    except (PsycopgError, RuntimeError):
        return {
            "available": False,
            "ready": False,
            "missing": {"tables": [], "columns": []},
        }
    return {
        "available": True,
        "ready": not missing["tables"] and not missing["columns"],
        "missing": missing,
        "checked_at": time.time(),
    }
