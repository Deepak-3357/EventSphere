"""Health-check endpoints."""

import time

from flask import Blueprint, jsonify

from app import schema_contract


health_bp = Blueprint("health", __name__)

# The readiness probe reads information_schema on every call, so results are
# cached briefly. Negative results are cached too, which keeps a schema that is
# behind the deployed code visible within seconds without turning the probe
# into an unauthenticated database-query amplifier.
SCHEMA_CACHE_SECONDS = 15
_schema_cache = {"checked_at": None, "report": None}


def reset_schema_cache():
    """Forget the cached readiness report (used by tests and after a migration)."""

    _schema_cache["checked_at"] = None
    _schema_cache["report"] = None


def _schema_report():
    now = time.monotonic()
    cached = _schema_cache["report"]
    if cached is not None and now - _schema_cache["checked_at"] < SCHEMA_CACHE_SECONDS:
        return cached
    report = schema_contract.schema_status()
    _schema_cache["checked_at"] = now
    _schema_cache["report"] = report
    return report


@health_bp.get("/health")
def health_check():
    """Return a lightweight liveness response for the API."""

    return jsonify({"status": "ok", "service": "EventSphere API"})


@health_bp.get("/health/schema")
def schema_health_check():
    """Readiness probe: does the database schema match this deployment?

    A migration that has not been applied is a deployment fault, not a request
    fault. Reporting it here keeps it from reaching users as a generic "the
    request could not be completed" on every event page. Only object names are
    disclosed -- no rows, no data, no connection detail.
    """

    report = _schema_report()
    if not report["available"]:
        return (
            jsonify(
                {
                    "status": "degraded",
                    "schema": "unavailable",
                    "service": "EventSphere API",
                    "message": "The database could not be inspected for schema readiness.",
                }
            ),
            503,
        )
    if not report["ready"]:
        return (
            jsonify(
                {
                    "status": "degraded",
                    "schema": "outdated",
                    "service": "EventSphere API",
                    "message": (
                        "The database schema is behind the deployed code. "
                        "Apply the pending migrations in supabase/migrations/ before serving traffic."
                    ),
                    "missing": report["missing"],
                }
            ),
            503,
        )
    return jsonify({"status": "ok", "schema": "current", "service": "EventSphere API"})
