"""Event pass and attendance scanner endpoints."""

import logging

from flask import Blueprint, g, request
from psycopg import DatabaseError

from app.routes.auth import require_auth, require_role
from app.services import attendance_service, event_service
from app.utils.responses import error, success


attendance_bp = Blueprint("attendance", __name__)
logger = logging.getLogger(__name__)


@attendance_bp.get("/registrations/<registration_id>/pass")
@require_auth
@require_role("student")
def event_pass(registration_id):
    try:
        return success(attendance_service.get_event_pass(registration_id, g.current_user["id"]))
    except attendance_service.AttendanceError as exc:
        return error(exc.code, exc.message, exc.status)
    except DatabaseError as exc:
        logger.error("event_pass_failed stage=database exception=%s", type(exc).__name__)
        return error("DATABASE_ERROR", "Event pass could not be loaded", 500)
    except Exception as exc:
        logger.error("event_pass_failed stage=unexpected exception=%s", type(exc).__name__)
        return error("DATABASE_ERROR", "Event pass could not be loaded", 500)


@attendance_bp.get("/registrations/<registration_id>/attendance-code")
@require_auth
@require_role("student")
def attendance_code(registration_id):
    try:
        return success(attendance_service.get_attendance_code(registration_id, g.current_user["id"]))
    except attendance_service.AttendanceError as exc:
        return error(exc.code, exc.message, exc.status)
    except DatabaseError:
        return error("DATABASE_ERROR", "Attendance code could not be loaded", 500)


@attendance_bp.post("/attendance/check-in")
@require_auth
@require_role("organizer", "admin")
def check_in():
    body = request.get_json(silent=True) or {}
    if not isinstance(body.get("qr_payload"), str):
        return error("MALFORMED_QR", "qr_payload is required", 400)
    try:
        event_id = request.args.get("event_id") or body.get("event_id")
        result = attendance_service.check_in(
            body["qr_payload"],
            g.current_user["id"],
            g.current_profile["role"],
            event_id=event_id,
        )
        return success(result, status=201)
    except attendance_service.AttendanceError as exc:
        return error(exc.code, exc.message, exc.status)
    except DatabaseError:
        return error("DATABASE_ERROR", "Attendance could not be recorded", 500)


@attendance_bp.post("/attendance/manual-check-in")
@require_auth
@require_role("organizer", "admin")
def manual_check_in():
    body = request.get_json(silent=True) or {}
    if not isinstance(body.get("event_id"), str) or not isinstance(body.get("code"), str):
        return error("INVALID_ATTENDANCE_CODE", "event_id and a six-digit code are required", 400)
    try:
        result = attendance_service.manual_check_in(
            body["event_id"], body["code"], g.current_user["id"], g.current_profile["role"]
        )
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
