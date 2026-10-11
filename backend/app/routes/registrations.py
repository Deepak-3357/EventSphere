"""Student registration and participant-management REST endpoints."""

from flask import Blueprint, g, request
from psycopg import DatabaseError
from psycopg.errors import UniqueViolation

from app.routes.auth import require_auth, require_role
from app.services import event_service, registration_service
from app.services.registration_service import RegistrationError
from app.utils.responses import error, success


registrations_bp = Blueprint("registrations", __name__)


def _database_error():
    return error("DATABASE_ERROR", "The registration request could not be completed.", 500)


def _registration_error(exc):
    return error(exc.code, exc.message, exc.status)


@registrations_bp.post("/events/<event_id>/register")
@require_auth
@require_role("student")
def register(event_id):
    try:
        registration = registration_service.register_student(event_id, g.current_user["id"], request.get_json(silent=True) or {})
        return success(
            {
                "registration_id": registration["id"],
                "event_id": registration["event_id"],
                "status": registration["status"],
                "registered_at": registration["registered_at"],
                "participation_type": registration["participation_type"],
                "team_id": registration.get("team_id"),
            },
            201,
        )
    except RegistrationError as exc:
        return _registration_error(exc)
    except UniqueViolation:
        return error("ALREADY_REGISTERED", "You are already registered for this event", 409)
    except DatabaseError:
        return _database_error()


@registrations_bp.delete("/events/<event_id>/register")
@require_auth
@require_role("student")
def cancel_registration(event_id):
    try:
        return success(registration_service.cancel_student_registration(event_id, g.current_user["id"]))
    except RegistrationError as exc:
        return _registration_error(exc)
    except DatabaseError:
        return _database_error()


@registrations_bp.get("/my-registrations")
@require_auth
@require_role("student")
def my_registrations():
    try:
        status = request.args.get("status")
        upcoming = request.args.get("upcoming", "false").lower() == "true"
        return success(registration_service.list_student_registrations(g.current_user["id"], status, upcoming))
    except RegistrationError as exc:
        return _registration_error(exc)
    except DatabaseError:
        return _database_error()


@registrations_bp.get("/events/<event_id>/registrations")
@require_auth
@require_role("organizer", "admin")
def event_registrations(event_id):
    try:
        event_id = event_service.parse_uuid(event_id, "event_id")
        event = event_service.get_event(event_id)
        if not event:
            return error("NOT_FOUND", "Event not found", 404)
        if g.current_profile["role"] == "organizer" and event["organizer"]["id"] != g.current_user["id"]:
            return error("FORBIDDEN", "You may only view registrations for your own events", 403)
        status = request.args.get("status")
        return success(registration_service.list_event_registrations(event_id, status))
    except (RegistrationError, ValueError) as exc:
        if isinstance(exc, RegistrationError):
            return _registration_error(exc)
        return error("VALIDATION_ERROR", str(exc), 422)
    except DatabaseError:
        return _database_error()


@registrations_bp.get("/registrations")
@require_auth
@require_role("admin")
def all_registrations():
    try:
        return success(
            registration_service.list_all_registrations(
                event_id=request.args.get("event_id"),
                status=request.args.get("status"),
                student_id=request.args.get("student_id"),
            )
        )
    except RegistrationError as exc:
        return _registration_error(exc)
    except DatabaseError:
        return _database_error()


@registrations_bp.get("/registrations/<registration_id>")
@require_auth
def get_registration(registration_id):
    try:
        registration = registration_service.get_registration(registration_id)
        if not registration:
            return error("NOT_FOUND", "Registration not found", 404)
        role = g.current_profile["role"]
        is_student_owner = role == "student" and registration["student_id"] == g.current_user["id"]
        is_event_owner = role == "organizer" and registration["event"]["id"] and _owns_event(registration["event"]["id"])
        if role != "admin" and not is_student_owner and not is_event_owner:
            return error("NOT_FOUND", "Registration not found", 404)
        return success(registration)
    except RegistrationError as exc:
        return _registration_error(exc)
    except DatabaseError:
        return _database_error()


def _owns_event(event_id):
    event = event_service.get_event(event_id)
    return bool(event and event["organizer"]["id"] == g.current_user["id"])
