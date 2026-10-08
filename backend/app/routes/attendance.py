"""Event pass and attendance scanner endpoints."""

from flask import Blueprint, g, request
from psycopg import DatabaseError

from app.routes.auth import require_auth, require_role
from app.services import attendance_service, event_service
from app.utils.responses import error, success


attendance_bp = Blueprint("attendance", __name__)


@attendance_bp.get("/registrations/<registration_id>/pass")
@require_auth
@require_role("student")
def event_pass(registration_id):
    try:
        return success(attendance_service.get_event_pass(registration_id, g.current_user["id"]))
    except attendance_service.AttendanceError as exc:
        return error(exc.code, exc.message, exc.status)
    except DatabaseError:
        return error("DATABASE_ERROR", "Event pass could not be loaded", 500)


@attendance_bp.post("/attendance/check-in")
@require_auth
@require_role("organizer", "admin")
def check_in():
    body = request.get_json(silent=True) or {}
    if not isinstance(body.get("qr_payload"), str):
        return error("MALFORMED_QR", "qr_payload is required", 400)
    try:
        result = attendance_service.check_in(body["qr_payload"], g.current_user["id"], g.current_profile["role"])
        return success(result, status=201)
    except attendance_service.AttendanceError as exc:
        return error(exc.code, exc.message, exc.status)
    except DatabaseError:
        return error("DATABASE_ERROR", "Attendance could not be recorded", 500)


@attendance_bp.get("/events/<event_id>/attendance")
@require_auth
@require_role("organizer", "admin")
def event_attendance(event_id):
    try:
        event = event_service.get_event(event_id)
        if not event:
            return error("EVENT_NOT_FOUND", "Event not found", 404)
        if g.current_profile["role"] == "organizer" and str(event["organizer"]["id"]) != str(g.current_user["id"]):
            return error("FORBIDDEN", "You do not own this event", 403)
        return success(attendance_service.list_event_attendance(event_id))
    except attendance_service.AttendanceError as exc:
        return error(exc.code, exc.message, exc.status)
    except DatabaseError:
        return error("DATABASE_ERROR", "Attendance could not be loaded", 500)
