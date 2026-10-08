"""Role-scoped dashboard endpoints."""

from flask import Blueprint, g
from psycopg import DatabaseError

from app.routes.auth import require_auth, require_role
from app.services import dashboard_service
from app.utils.responses import error, success

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.get("/dashboard/student")
@require_auth
@require_role("student")
def student_dashboard():
    try:
        return success(dashboard_service.student_dashboard(g.current_user["id"]))
    except DatabaseError:
        return error("DATABASE_ERROR", "Student dashboard could not be loaded", 500)


@dashboard_bp.get("/dashboard/organizer")
@require_auth
@require_role("organizer")
def organizer_dashboard():
    try:
        return success(dashboard_service.organizer_dashboard(g.current_user["id"]))
    except DatabaseError:
        return error("DATABASE_ERROR", "Organizer dashboard could not be loaded", 500)


@dashboard_bp.get("/dashboard/admin")
@require_auth
@require_role("admin")
def admin_dashboard():
    try:
        return success(dashboard_service.admin_dashboard())
    except DatabaseError:
        return error("DATABASE_ERROR", "Admin dashboard could not be loaded", 500)
