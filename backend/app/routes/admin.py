"""Master Admin user-management endpoints."""

from flask import Blueprint, g, request
from psycopg import DatabaseError

from app.routes.auth import require_auth, require_master_admin
from app.services import admin_service
from app.utils.responses import error, success

admin_bp = Blueprint("admin", __name__)


def _handle(exc):
    return error(exc.code, exc.message, exc.status)


@admin_bp.get("/users")
@require_auth
@require_master_admin
def list_users():
    try:
        return success(admin_service.list_profiles(request.args.get("search", "").strip(), request.args.get("role", "").strip()))
    except admin_service.AdminServiceError as exc:
        return _handle(exc)
    except DatabaseError:
        return error("DATABASE_ERROR", "User records could not be loaded", 500)


@admin_bp.post("/users")
@require_auth
@require_master_admin
def create_user():
    try:
        payload = request.get_json(silent=True)
        if isinstance(payload, dict):
            payload = {key: value for key, value in payload.items() if key != "is_master_admin"}
        return success(admin_service.create_privileged_user(payload), 201)
    except admin_service.AdminServiceError as exc:
        return _handle(exc)
    except DatabaseError:
        return error("DATABASE_ERROR", "The account could not be created", 500)
