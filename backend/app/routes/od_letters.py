"""Student OD letter APIs and minimal public verification."""

from flask import Blueprint, g, request, send_file
from psycopg import DatabaseError

from app.routes.auth import require_auth, require_role
from app.services import od_letter_service
from app.utils.responses import error, success

od_letters_bp = Blueprint("od_letters", __name__)


def _handle(exc):
    return error(exc.code, exc.message, exc.status)


@od_letters_bp.post("/registrations/<registration_id>/od-letter")
@require_auth
@require_role("student")
def create_od_letter(registration_id):
    try:
        return success(od_letter_service.create_or_get(registration_id, g.current_user["id"]), 201)
    except od_letter_service.ODLetterError as exc:
        return _handle(exc)
    except DatabaseError:
        return error("DATABASE_ERROR", "OD letter could not be generated", 500)


@od_letters_bp.get("/registrations/<registration_id>/od-letter")
@require_auth
@require_role("student")
def get_od_letter(registration_id):
    try:
        letter = od_letter_service.get_for_registration(registration_id, g.current_user["id"])
        return success(letter)
    except od_letter_service.ODLetterError as exc:
        return _handle(exc)
    except DatabaseError:
        return error("DATABASE_ERROR", "OD letter could not be loaded", 500)


@od_letters_bp.get("/od-letters/<letter_id>/download")
@require_auth
@require_role("student")
def download_od_letter(letter_id):
    try:
        letter = od_letter_service.get_for_student(letter_id, g.current_user["id"])
        pdf = od_letter_service.generate_pdf(letter)
        return send_file(pdf, mimetype="application/pdf", as_attachment=True, download_name=f"{letter['letter_number']}.pdf")
    except od_letter_service.ODLetterError as exc:
        return _handle(exc)
    except DatabaseError:
        return error("DATABASE_ERROR", "OD letter could not be downloaded", 500)


@od_letters_bp.get("/od-letters/<letter_id>/verify")
def verify_od_letter(letter_id):
    try:
        return success(od_letter_service.verify_public(letter_id, request.args.get("token")))
    except od_letter_service.ODLetterError as exc:
        return _handle(exc)
    except DatabaseError:
        return error("DATABASE_ERROR", "OD letter verification failed", 500)
