"""Supabase Auth token verification and role-protected validation endpoints."""

from functools import wraps
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from flask import Blueprint, current_app, g, jsonify, request

from app.db import get_connection
from app.utils.responses import error


auth_bp = Blueprint("auth", __name__)


def _unauthorized(message="Authentication required"):
    return error("UNAUTHORIZED", message, 401)


def _extract_bearer_token():
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def verify_access_token(token):
    """Verify a Supabase access token through the Auth user endpoint."""

    supabase_url = current_app.config.get("SUPABASE_URL", "").rstrip("/")
    publishable_key = current_app.config.get("SUPABASE_ANON_KEY", "")
    if not supabase_url or not publishable_key:
        return None

    auth_request = Request(
        f"{supabase_url}/auth/v1/user",
        headers={
            "apikey": publishable_key,
            "Authorization": f"Bearer {token}",
        },
        method="GET",
    )
    try:
        with urlopen(auth_request, timeout=5) as response:
            if response.status != 200:
                return None
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, ValueError):
        return None


def _load_profile(user_id):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select id, full_name, email, phone, role, department, year,
                       created_at, updated_at
                from profiles
                where id = %s
                """,
                (user_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            columns = [description.name for description in cursor.description]
            return dict(zip(columns, row))


def require_auth(view):
    """Require a valid Supabase bearer token and load its profile."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        token = _extract_bearer_token()
        if not token:
            return _unauthorized()

        user = verify_access_token(token)
        if not user or not user.get("id"):
            return _unauthorized("Invalid or expired session")

        profile = _load_profile(user["id"])
        if not profile:
            return error("FORBIDDEN", "Authenticated profile is not available", 403)

        g.current_user = user
        g.current_profile = profile
        return view(*args, **kwargs)

    return wrapped


def require_role(*allowed_roles):
    """Require one of the roles loaded from the database profile."""

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            profile = getattr(g, "current_profile", None)
            if not profile or profile.get("role") not in allowed_roles:
                return error("FORBIDDEN", "Insufficient permissions", 403)
            return view(*args, **kwargs)

        return wrapped

    return decorator


@auth_bp.get("/me")
@require_auth
def current_profile():
    """Return the verified user's safe profile fields."""

    return jsonify({"user": {"id": g.current_user["id"], "email": g.current_user.get("email")}, "profile": g.current_profile})


@auth_bp.get("/student-test")
@require_auth
@require_role("student")
def student_test():
    return jsonify({"status": "ok", "role": "student"})


@auth_bp.get("/organizer-test")
@require_auth
@require_role("organizer")
def organizer_test():
    return jsonify({"status": "ok", "role": "organizer"})


@auth_bp.get("/admin-test")
@require_auth
@require_role("admin")
def admin_test():
    return jsonify({"status": "ok", "role": "admin"})
