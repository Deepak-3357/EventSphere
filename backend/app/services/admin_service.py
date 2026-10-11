"""Master-Admin-only user administration backed by Supabase Admin Auth."""

import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from flask import current_app

from app.db import get_connection


class AdminServiceError(Exception):
    def __init__(self, code, message, status=409):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


def list_profiles(search="", role=""):
    conditions, params = [], []
    if search:
        conditions.append("(email ilike %s or full_name ilike %s)")
        params.extend([f"%{search[:100]}%", f"%{search[:100]}%"])
    if role:
        if role not in {"student", "organizer", "admin"}:
            raise AdminServiceError("INVALID_ROLE", "role must be student, organizer, or admin", 422)
        conditions.append("role=%s")
        params.append(role)
    where = f" where {' and '.join(conditions)}" if conditions else ""
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(f"""select id, full_name, email, phone, role, department, year, is_master_admin, created_at, updated_at
                              from profiles{where} order by created_at desc""", params)
            rows = cursor.fetchall()
            return [{
                "id": str(row[0]), "full_name": row[1], "email": row[2], "phone": row[3],
                "role": row[4], "department": row[5], "year": row[6],
                "is_master_admin": row[7], "created_at": row[8].isoformat(), "updated_at": row[9].isoformat(),
            } for row in rows]


def _admin_request(path, method="GET", payload=None):
    base_url = current_app.config.get("SUPABASE_URL", "").rstrip("/")
    service_key = current_app.config.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not base_url or not service_key:
        raise AdminServiceError("ADMIN_AUTH_NOT_CONFIGURED", "Server-side Supabase Admin Auth is not configured", 503)
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(f"{base_url}/auth/v1/{path.lstrip('/')}", data=body, method=method, headers={
        "apikey": service_key, "Authorization": f"Bearer {service_key}", "Content-Type": "application/json",
    })
    try:
        with urlopen(request, timeout=10) as response:
            raw = response.read()
            return json.loads(raw.decode("utf-8")) if raw else {}
    except HTTPError as exc:
        if exc.code in {400, 422}:
            raise AdminServiceError("ADMIN_AUTH_REJECTED", "Supabase rejected the account configuration", 422) from exc
        raise AdminServiceError("ADMIN_AUTH_UNAVAILABLE", "Supabase Admin Auth could not complete the request", 503) from exc
    except (URLError, TimeoutError) as exc:
        raise AdminServiceError("ADMIN_AUTH_UNAVAILABLE", "Supabase Admin Auth is unavailable", 503) from exc


def _find_auth_user(email):
    users = _admin_request("admin/users?page=1&per_page=100").get("users", [])
    return next((user for user in users if (user.get("email") or "").lower() == email.lower()), None)


def create_privileged_user(payload):
    if not isinstance(payload, dict):
        raise AdminServiceError("VALIDATION_ERROR", "Request body must be a JSON object", 422)
    email = payload.get("email", "").strip().lower()
    full_name = payload.get("full_name", "").strip()
    password = payload.get("password", "")
    role = payload.get("role")
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise AdminServiceError("VALIDATION_ERROR", "A valid email is required", 422)
    if not 2 <= len(full_name) <= 160:
        raise AdminServiceError("VALIDATION_ERROR", "full_name must be between 2 and 160 characters", 422)
    if role not in {"organizer", "admin"}:
        raise AdminServiceError("INVALID_ROLE", "Only organizer or ordinary admin accounts can be created", 422)
    if not isinstance(password, str) or len(password) < 6:
        raise AdminServiceError("WEAK_PASSWORD", "Supabase requires a password of at least 6 characters", 422)
    if _find_auth_user(email):
        raise AdminServiceError("ACCOUNT_EXISTS", "An Auth account with this email already exists", 409)
    user = _admin_request("admin/users", "POST", {
        "email": email, "password": password, "email_confirm": True,
        "user_metadata": {"full_name": full_name},
    }).get("user")
    if not user or not user.get("id"):
        raise AdminServiceError("ADMIN_AUTH_UNAVAILABLE", "Supabase did not return the created user", 503)
    auth_id = str(user["id"])
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("select id from profiles where lower(email)=lower(%s)", (email,))
            existing = cursor.fetchone()
            if existing and str(existing[0]) != auth_id:
                raise AdminServiceError("PROFILE_ID_MISMATCH", "An existing profile uses this email with a different Auth UUID", 409)
            if existing:
                cursor.execute("update profiles set full_name=%s, role=%s, is_master_admin=false, updated_at=now() where id=%s", (full_name, role, auth_id))
            else:
                cursor.execute("insert into profiles(id, full_name, email, role) values(%s,%s,%s,%s)", (auth_id, full_name, email, role))
            cursor.execute("select id, full_name, email, role, is_master_admin from profiles where id=%s", (auth_id,))
            row = cursor.fetchone()
            if not row or str(row[0]) != auth_id or row[3] != role:
                raise AdminServiceError("PROFILE_SYNC_FAILED", "Auth user was created but its profile could not be verified", 500)
            return {"id": str(row[0]), "full_name": row[1], "email": row[2], "role": row[3], "is_master_admin": row[4]}
