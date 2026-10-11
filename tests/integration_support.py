"""Safe, explicit fixtures for tests that write to the Supabase database."""

import os
import re
import unittest
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def require_integration_database():
    """Require an explicit local-test opt-in before any test writes to the DB."""
    if os.getenv("FLASK_ENV", "development").lower() == "production":
        raise RuntimeError("Refusing integration tests while FLASK_ENV=production")
    if os.getenv("EVENTSPHERE_TEST_DATABASE") != "local":
        raise unittest.SkipTest("Set EVENTSPHERE_TEST_DATABASE=local for database integration tests")
    if os.getenv("EVENTSPHERE_TEST_DB_WRITES") != "ALLOW_EVENTSPHERE_LOCAL_DB":
        raise unittest.SkipTest("Set EVENTSPHERE_TEST_DB_WRITES=ALLOW_EVENTSPHERE_LOCAL_DB for test writes")
    host = os.getenv("SUPABASE_DB_HOST", "")
    password = os.getenv("SUPABASE_DB_PASSWORD", "")
    if not host or not password:
        raise unittest.SkipTest("Database credentials are not configured")
    project_ref = os.getenv("EVENTSPHERE_TEST_PROJECT_REF", "")
    url_ref = re.search(r"https?://([^.]+)\.supabase\.co", os.getenv("SUPABASE_URL", ""))
    if not project_ref or not url_ref or project_ref != url_ref.group(1):
        raise unittest.SkipTest("Set EVENTSPHERE_TEST_PROJECT_REF to the explicitly approved local Supabase project")


def resolve_profile_id(email, fallback):
    """Use the current Auth-linked profile in opted-in integration runs."""
    if os.getenv("EVENTSPHERE_TEST_DATABASE") != "local":
        return fallback
    from app.db import get_connection

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("select id from public.profiles where lower(email)=lower(%s)", (email,))
            row = cursor.fetchone()
    if not row:
        raise RuntimeError(f"Required integration profile is missing: {email}")
    return str(row[0])
