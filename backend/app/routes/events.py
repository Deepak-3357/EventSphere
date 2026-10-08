"""REST endpoints for EventSphere event management."""

from datetime import date
from xml.etree.ElementTree import Element, SubElement, tostring

from flask import Blueprint, Response, g, request
from psycopg import DatabaseError

from app.routes.auth import _extract_bearer_token, _load_profile, require_auth, require_role, verify_access_token
from app.services import event_service
from app.utils.responses import error, success


events_bp = Blueprint("events", __name__)


@events_bp.get("/export.xml")
def export_events_xml():
    """Small public XML representation of the published event catalog."""
    try:
        events, _ = event_service.list_events({"page": 1, "limit": 100, "search": "", "category": "", "venue": "", "date": None, "status": "published"})
        root = Element("events", {"source": "EventSphere"})
        for event in events:
            item = SubElement(root, "event", {"id": str(event["id"])})
            for name, value in (("title", event["title"]), ("description", event.get("description") or ""),
                                ("date", event["event_date"]), ("start_time", event["start_time"]),
                                ("end_time", event["end_time"]), ("status", event["status"]),
                                ("venue", event["venue"]["name"]), ("location", event["venue"]["location"]),
                                ("category", event["category"]["name"])):
                SubElement(item, name).text = str(value)
        return Response(tostring(root, encoding="utf-8", xml_declaration=True), content_type="application/xml; charset=utf-8")
    except DatabaseError:
        return _handle_database_error()


def _optional_identity():
    token = _extract_bearer_token()
    if not token:
        return None, None
    user = verify_access_token(token)
    if not user or not user.get("id"):
        return None, error("UNAUTHORIZED", "Invalid or expired session", 401)
    profile = _load_profile(user["id"])
    if not profile:
        return None, error("FORBIDDEN", "Authenticated profile is not available", 403)
    return {"id": user["id"], "profile": profile}, None


def _filters(identity):
    try:
        page = int(request.args.get("page", 1))
        limit = int(request.args.get("limit", 10))
    except ValueError:
        raise ValueError("page and limit must be integers")
    if page < 1 or limit < 1 or limit > 100:
        raise ValueError("page must be at least 1 and limit must be between 1 and 100")

    requested_status = request.args.get("status")
    if requested_status and requested_status not in event_service.EVENT_STATUSES:
        raise ValueError("status must be one of draft, pending, published, cancelled, completed")
    role = identity["profile"]["role"] if identity else None
    if requested_status and requested_status != "published" and role is None:
        raise PermissionError("Authentication is required to view private event statuses")
    if requested_status and requested_status != "published" and role not in {"organizer", "admin"}:
        raise PermissionError("Only organizers and admins can view private event statuses")

    requested_date = request.args.get("date")
    if requested_date:
        try:
            date.fromisoformat(requested_date)
        except ValueError:
            raise ValueError("date must use YYYY-MM-DD format")

    return {
        "page": page,
        "limit": limit,
        "search": request.args.get("search", "").strip()[:200],
        "category": request.args.get("category", "").strip()[:100],
        "venue": request.args.get("venue", "").strip()[:100],
        "date": requested_date,
        "status": requested_status,
    }


def _handle_database_error():
    return error("DATABASE_ERROR", "The event request could not be completed.", 500)


@events_bp.get("")
def list_events():
    identity, auth_error = _optional_identity()
    if auth_error:
        return auth_error
    try:
        filters = _filters(identity)
        role = identity["profile"]["role"] if identity else None
        events, total = event_service.list_events(filters, role, identity["id"] if identity else None)
        return success(events, pagination={"page": filters["page"], "limit": filters["limit"], "total": total})
    except PermissionError as exc:
        return error("FORBIDDEN", str(exc), 403)
    except ValueError as exc:
        return error("VALIDATION_ERROR", str(exc), 422)
    except DatabaseError:
        return _handle_database_error()


@events_bp.get("/<event_id>")
def get_event(event_id):
    identity, auth_error = _optional_identity()
    if auth_error:
        return auth_error
    try:
        event_id = event_service.parse_uuid(event_id, "event_id")
        event = event_service.get_event(event_id)
        if not event:
            return error("NOT_FOUND", "Event not found", 404)
        role = identity["profile"]["role"] if identity else None
        is_owner = identity and event["organizer"]["id"] == identity["id"]
        if event["status"] != "published" and role != "admin" and not (role == "organizer" and is_owner):
            return error("NOT_FOUND", "Event not found", 404)
        if role == "student":
            event["is_registered"] = event_service.is_student_registered(event_id, identity["id"])
        return success(event)
    except ValueError as exc:
        return error("VALIDATION_ERROR", str(exc), 422)
    except DatabaseError:
        return _handle_database_error()


@events_bp.post("")
@require_auth
@require_role("organizer", "admin")
def create_event():
    try:
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return error("VALIDATION_ERROR", "Request body must be a JSON object", 422)
        event = event_service.create_event(payload, g.current_user["id"])
        return success(event, 201)
    except ValueError as exc:
        return error("VALIDATION_ERROR", str(exc), 422)
    except LookupError as exc:
        return error("NOT_FOUND", str(exc), 404)
    except DatabaseError:
        return _handle_database_error()


def _owned_or_admin(event):
    profile = g.current_profile
    return profile["role"] == "admin" or (profile["role"] == "organizer" and event["organizer"]["id"] == g.current_user["id"])


@events_bp.put("/<event_id>")
@require_auth
@require_role("organizer", "admin")
def update_event(event_id):
    try:
        event_id = event_service.parse_uuid(event_id, "event_id")
        existing = event_service.get_event(event_id)
        if not existing:
            return error("NOT_FOUND", "Event not found", 404)
        if not _owned_or_admin(existing):
            return error("FORBIDDEN", "You may only manage your own events", 403)
        payload = request.get_json(silent=True)
        event = event_service.update_event(event_id, payload)
        return success(event)
    except ValueError as exc:
        return error("VALIDATION_ERROR", str(exc), 422)
    except DatabaseError:
        return _handle_database_error()


@events_bp.delete("/<event_id>")
@require_auth
@require_role("organizer", "admin")
def delete_event(event_id):
    try:
        event_id = event_service.parse_uuid(event_id, "event_id")
        existing = event_service.get_event(event_id)
        if not existing:
            return error("NOT_FOUND", "Event not found", 404)
        if not _owned_or_admin(existing):
            return error("FORBIDDEN", "You may only manage your own events", 403)
        event, cancelled = event_service.delete_event(event_id)
        if cancelled:
            return success(event)
        return success({"id": event_id, "deleted": True})
    except ValueError as exc:
        return error("VALIDATION_ERROR", str(exc), 422)
    except DatabaseError:
        return _handle_database_error()


@events_bp.patch("/<event_id>/publish")
@require_auth
@require_role("organizer", "admin")
def publish_event(event_id):
    return _change_event_status(event_id, "published")


@events_bp.patch("/<event_id>/cancel")
@require_auth
@require_role("organizer", "admin")
def cancel_event(event_id):
    return _change_event_status(event_id, "cancelled")


def _change_event_status(event_id, new_status):
    try:
        event_id = event_service.parse_uuid(event_id, "event_id")
        existing = event_service.get_event(event_id)
        if not existing:
            return error("NOT_FOUND", "Event not found", 404)
        if not _owned_or_admin(existing):
            return error("FORBIDDEN", "You may only manage your own events", 403)
        if new_status == "published":
            event_service.validate_event_payload(
                {
                    "title": existing["title"],
                    "description": existing["description"],
                    "category_id": existing["category"]["id"],
                    "venue_id": existing["venue"]["id"],
                    "event_date": existing["event_date"],
                    "start_time": existing["start_time"],
                    "end_time": existing["end_time"],
                    "capacity": existing["capacity"],
                    "registration_deadline": existing["registration_deadline"],
                    "image_url": existing["image_url"],
                },
                requested_status=new_status,
            )
        event = event_service.change_status(event_id, new_status)
        return success(event)
    except ValueError as exc:
        return error("VALIDATION_ERROR", str(exc), 422)
    except DatabaseError:
        return _handle_database_error()


