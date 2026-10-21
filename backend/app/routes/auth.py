"""Supabase Auth token verification and role-protected validation endpoints."""

from functools import wraps
import hashlib
import json
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from flask import Blueprint, current_app, g, jsonify, request

from app.db import get_connection
from app.utils.responses import error


auth_bp = Blueprint("auth", __name__)

_TOKEN_CACHE = {}
_PROFILE_CACHE = {}
TOKEN_CACHE_TTL = 30
PROFILE_CACHE_TTL = 30
MAX_CACHE_ENTRIES = 1000


def _prune_cache(cache, max_entries=MAX_CACHE_ENTRIES):
    if len(cache) >= max_entries:
        now = time.monotonic()
        expired = [k for k, v in cache.items() if v[1] <= now]
        for k in expired:
            cache.pop(k, None)
        if len(cache) >= max_entries:
            cache.clear()


def clear_auth_cache():
    _TOKEN_CACHE.clear()
    _PROFILE_CACHE.clear()


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

    now = time.monotonic()
    token_key = hashlib.sha256(token.encode("utf-8")).hexdigest()
    cached = _TOKEN_CACHE.get(token_key)
    if cached and cached[1] > now:
        return cached[0]

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
            data = json.loads(response.read().decode("utf-8"))
            _prune_cache(_TOKEN_CACHE)
            _TOKEN_CACHE[token_key] = (data, now + TOKEN_CACHE_TTL)
            return data
    except (HTTPError, URLError, TimeoutError, ValueError):
        return None


def _load_profile(user_id):
    now = time.monotonic()
    user_key = str(user_id)
    cached = _PROFILE_CACHE.get(user_key)
    if cached and cached[1] > now:
        return cached[0]

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select id, full_name, email, phone, role, department, year,
                       created_at, updated_at, is_master_admin
                from profiles
                where id = %s
                """,
                (user_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            columns = [description.name for description in cursor.description]
            profile = dict(zip(columns, row))
            _prune_cache(_PROFILE_CACHE)
            _PROFILE_CACHE[user_key] = (profile, now + PROFILE_CACHE_TTL)
            return profile


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


def require_master_admin(view):
    """Require the database-backed single Master Admin designation."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        profile = getattr(g, "current_profile", None)
        if not profile or profile.get("role") != "admin" or profile.get("is_master_admin") is not True:
            return error("FORBIDDEN", "Master Admin permissions required", 403)
        return view(*args, **kwargs)

    return wrapped


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
