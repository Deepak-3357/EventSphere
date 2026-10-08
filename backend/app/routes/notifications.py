"""Authenticated notification-center endpoints."""

from uuid import UUID

from flask import Blueprint, g, request
from psycopg import DatabaseError

from app.services import notification_service
from app.utils.responses import error, success


notifications_bp = Blueprint("notifications", __name__)


def _auth_required(view):
    from app.routes.auth import require_auth

    return require_auth(view)


def _parse_uuid(value):
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError):
        return None


@notifications_bp.get("/notifications")
@_auth_required
def list_notifications():
    try:
        page = int(request.args.get("page", 1))
        limit = int(request.args.get("limit", 10))
        if page < 1 or limit < 1 or limit > 100:
            raise ValueError
        unread_value = request.args.get("unread")
        unread = None
        if unread_value is not None:
            if unread_value.lower() not in {"true", "false"}:
                return error("VALIDATION_ERROR", "unread must be true or false", 422)
            unread = unread_value.lower() == "true"
        notification_type = request.args.get("type")
        items, total = notification_service.list_user_notifications(
            g.current_user["id"], page, limit, unread, notification_type
        )
        return success(items, pagination={"page": page, "limit": limit, "total": total})
    except ValueError as exc:
        return error("VALIDATION_ERROR", str(exc), 422)
    except DatabaseError:
        return error("DATABASE_ERROR", "Notifications could not be loaded", 500)


@notifications_bp.get("/notifications/unread-count")
@_auth_required
def unread_count():
    try:
        return success({"unread_count": notification_service.unread_count(g.current_user["id"])})
    except DatabaseError:
        return error("DATABASE_ERROR", "Unread notifications could not be loaded", 500)


@notifications_bp.patch("/notifications/<notification_id>/read")
@_auth_required
def mark_read(notification_id):
    notification_id = _parse_uuid(notification_id)
    if not notification_id:
        return error("VALIDATION_ERROR", "notification_id must be a valid UUID", 422)
    try:
        notification = notification_service.mark_notification_read(notification_id, g.current_user["id"])
        if not notification:
            return error("NOT_FOUND", "Notification not found", 404)
        return success(notification)
    except DatabaseError:
        return error("DATABASE_ERROR", "Notification could not be updated", 500)


@notifications_bp.patch("/notifications/read-all")
@_auth_required
def mark_all_read():
    try:
        return success({"updated_count": notification_service.mark_all_read(g.current_user["id"])})
    except DatabaseError:
        return error("DATABASE_ERROR", "Notifications could not be updated", 500)
