"""Provision the EventSphere development accounts through Supabase Admin Auth.

This script is intentionally opt-in and local-only. It never prints passwords or
credentials. It also re-homes the legacy seed profile to the Auth UUID while
preserving rows that reference that profile.
"""

import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
load_dotenv(ROOT / ".env")
load_dotenv(ROOT / ".env.local")

ACCOUNTS = (
    ("Admin@gmail.com", "EVENTSPHERE_MASTER_ADMIN_PASSWORD", "Master Administrator", "admin", "Administration", True),
    ("admin@example.test", "EVENTSPHERE_ADMIN_TEST_PASSWORD", "System Administrator", "admin", "Administration", False),
    ("rohan.organizer@example.test", "EVENTSPHERE_ORGANIZER_TEST_PASSWORD", "Rohan Iyer", "organizer", "Computer Science", False),
)


def request_json(url, key, method="GET", payload=None):
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(url, data=body, method=method, headers={
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    })
    try:
        with urlopen(request, timeout=10) as response:
            raw = response.read()
            return response.status, json.loads(raw.decode("utf-8")) if raw else {}
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Supabase Admin Auth request failed with HTTP {exc.code}: {detail[:300]}") from exc


def find_auth_user(base_url, key, email):
    page = 1
    while True:
        _, body = request_json(f"{base_url}/auth/v1/admin/users?page={page}&per_page=100", key)
        users = body.get("users", [])
        for user in users:
            if (user.get("email") or "").lower() == email.lower():
                return user
        if len(users) < 100:
            return None
        page += 1


def temporarily_release_seed_profile(email):
    """Free a seeded profile email so Supabase's Auth trigger can insert safely."""
    from app.db import get_connection

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("select id from public.profiles where lower(email)=lower(%s)", (email,))
            row = cursor.fetchone()
            if not row:
                return None
            profile_id = str(row[0])
            temporary_email = f"legacy+{profile_id}@invalid.eventsphere.local"
            cursor.execute("update public.profiles set email=%s, updated_at=now() where id=%s", (temporary_email, profile_id))
            return profile_id


def restore_seed_profile_email(profile_id, email):
    from app.db import get_connection

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("update public.profiles set email=%s, updated_at=now() where id=%s", (email, profile_id))


def main():
    if os.getenv("EVENTSPHERE_DEV_MODE") != "1" or os.getenv("EVENTSPHERE_PROVISION_CONFIRM") != "CREATE_LOCAL_TEST_ACCOUNTS":
        raise SystemExit("Refusing to run. Set EVENTSPHERE_DEV_MODE=1 and EVENTSPHERE_PROVISION_CONFIRM=CREATE_LOCAL_TEST_ACCOUNTS in ignored local environment configuration.")
    if os.getenv("FLASK_ENV", "development").lower() == "production":
        raise SystemExit("Refusing to run with FLASK_ENV=production.")
    base_url = os.getenv("SUPABASE_URL", "").rstrip("/")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    if not base_url or not service_key:
        raise SystemExit("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in ignored local environment configuration.")
    passwords = {email: os.getenv(password_var, "") for email, password_var, *_ in ACCOUNTS}
    if any(len(password) < 6 for password in passwords.values()):
        raise SystemExit("Supabase requires at least six password characters. The requested local Master Admin password '1234' is too short; set a longer local-only password in .env.local. Passwords are never read from source control.")

    from app.db import get_connection

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("select email from public.profiles where is_master_admin=true")
            current_master = cursor.fetchone()
            for email, _, full_name, role, department, is_master in ACCOUNTS:
                if is_master and current_master and current_master[0].lower() != email.lower():
                    raise RuntimeError("A different Master Admin is already designated; refusing to create or promote another account.")
                user = find_auth_user(base_url, service_key, email)
                if user is None:
                    released_profile_id = temporarily_release_seed_profile(email)
                    try:
                        _, body = request_json(f"{base_url}/auth/v1/admin/users", service_key, "POST", {
                            "email": email,
                            "password": passwords[email],
                            "email_confirm": True,
                            "user_metadata": {"full_name": full_name, "department": department},
                        })
                    except Exception:
                        if released_profile_id:
                            restore_seed_profile_email(released_profile_id, email)
                        raise
                    user = body.get("user", body)
                    print(f"Created Auth user for {email}.")
                else:
                    released_profile_id = None
                    request_json(f"{base_url}/auth/v1/admin/users/{user['id']}", service_key, "PUT", {
                        "password": passwords[email], "email_confirm": True,
                    })
                    print(f"Reused Auth user for {email}.")

                auth_id = str(user["id"])
                if released_profile_id:
                    cursor.execute("select id, full_name, phone, department, year from public.profiles where id=%s", (released_profile_id,))
                else:
                    cursor.execute("select id, full_name, phone, department, year from public.profiles where lower(email)=lower(%s)", (email,))
                profile = cursor.fetchone()
                if profile and str(profile[0]) != auth_id:
                    old_id = str(profile[0])
                    cursor.execute("delete from public.profiles where id=%s", (auth_id,))
                    cursor.execute("insert into public.profiles(id, full_name, email, phone, role, department, year, is_master_admin) values (%s,%s,%s,%s,%s,%s,%s,%s)", (auth_id, profile[1] or full_name, email, profile[2], role, profile[3] or department, profile[4], is_master))
                    for table, columns in {
                        "events": ("organizer_id",),
                        "registrations": ("student_id",),
                        "notifications": ("user_id",),
                        "attendance": ("student_id", "scanned_by"),
                        "od_letters": ("student_id",),
                    }.items():
                        for column in columns:
                            cursor.execute(f"update public.{table} set {column}=%s where {column}=%s", (auth_id, old_id))
                    # Keep the legacy seed row as a non-Auth fixture placeholder. Existing
                    # development data and integration fixtures may still reference its UUID.
                else:
                    cursor.execute("update public.profiles set role=%s, is_master_admin=%s, full_name=%s, department=%s, updated_at=now() where id=%s", (role, is_master, full_name, department, auth_id))
                cursor.execute("select id, role, is_master_admin from public.profiles where id=%s", (auth_id,))
                final = cursor.fetchone()
                if not final or str(final[0]) != auth_id or final[1] != role or final[2] != is_master:
                    raise RuntimeError(f"Profile verification failed for {email}.")
                print(f"Verified {email} with role {role}.")
    print("Local test-account provisioning completed.")


if __name__ == "__main__":
    main()
