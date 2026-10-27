"""Authenticated venue availability, booking, and admin management APIs."""

from flask import Blueprint, g, request
from psycopg import DatabaseError
from psycopg.errors import ExclusionViolation, UniqueViolation

from app.routes.auth import require_auth, require_role
from app.services import venue_service
from app.utils.responses import error, success


venues_management_bp = Blueprint("venues_management", __name__)


def _handle_service_error(exc):
    return error(exc.code, exc.message, exc.status)


@venues_management_bp.get("/manage")
@require_auth
@require_role("admin", "organizer")
def managed_venues():
    try:
        return success(venue_service.list_venues(include_inactive=True))
    except DatabaseError:
        return error("DATABASE_ERROR", "Venue records could not be loaded", 500)


@venues_management_bp.get("/calendar")
@require_auth
@require_role("admin", "organizer")
def calendar():
    try:
        selected_date = request.args.get("date")
        if not selected_date:
            return error("VALIDATION_ERROR", "date is required", 422)
        venues = venue_service.list_venues(include_inactive=True)
        include_details = g.current_profile["role"] == "admin"
        data = [venue_service.availability(item["id"], selected_date, include_details=include_details) for item in venues]
        return success({"date": selected_date, "venues": data})
    except venue_service.VenueServiceError as exc:
        return _handle_service_error(exc)
    except DatabaseError:
        return error("DATABASE_ERROR", "Venue availability could not be loaded", 500)


@venues_management_bp.get("/<venue_id>/availability")
@require_auth
@require_role("admin", "organizer")
def venue_availability(venue_id):
    try:
        selected_date = request.args.get("date")
        if not selected_date:
            return error("VALIDATION_ERROR", "date is required", 422)
        include_details = g.current_profile["role"] == "admin"
        return success(venue_service.availability(venue_id, selected_date, include_details=include_details))
    except venue_service.VenueServiceError as exc:
        return _handle_service_error(exc)
    except DatabaseError:
        return error("DATABASE_ERROR", "Venue availability could not be loaded", 500)


@venues_management_bp.post("/availability-check")
@require_auth
@require_role("organizer")
def restricted_availability():
    try:
        return success(venue_service.restricted_availability(request.get_json(silent=True)))
    except venue_service.VenueServiceError as exc:
        return _handle_service_error(exc)
    except DatabaseError:
        return error("DATABASE_ERROR", "Venue availability could not be checked", 500)


@venues_management_bp.post("/bookings")
@require_auth
@require_role("organizer", "admin")
def create_booking():
    try:
        booking = venue_service.create_booking(request.get_json(silent=True), g.current_user["id"], g.current_profile["role"])
        return success(booking, 201)
    except venue_service.VenueServiceError as exc:
        return _handle_service_error(exc)
    except (ExclusionViolation, UniqueViolation):
        return error("VENUE_CONFLICT", "The venue was booked by another request during this operation", 409)
    except DatabaseError:
        return error("DATABASE_ERROR", "The venue booking could not be completed", 500)


@venues_management_bp.get("/bookings")
@require_auth
@require_role("admin", "organizer")
def list_bookings():
    try:
        is_global = g.current_profile["role"] == "admin"
        return success(venue_service.list_bookings(None if is_global else g.current_user["id"], include_all=is_global))
    except DatabaseError:
        return error("DATABASE_ERROR", "Venue bookings could not be loaded", 500)


@venues_management_bp.get("/bookings/<booking_id>")
@require_auth
@require_role("admin", "organizer")
def get_booking(booking_id):
    try:
        booking = venue_service.get_booking(booking_id)
        if not booking:
            return error("NOT_FOUND", "Booking not found", 404)
        role = g.current_profile["role"]
        if role == "organizer" and booking["requester_id"] != g.current_user["id"]:
            return error("NOT_FOUND", "Booking not found", 404)
        return success(booking)
    except venue_service.VenueServiceError as exc:
        return _handle_service_error(exc)
    except DatabaseError:
        return error("DATABASE_ERROR", "The booking could not be loaded", 500)


@venues_management_bp.patch("/bookings/<booking_id>/cancel")
@require_auth
@require_role("admin", "organizer")
def cancel_booking(booking_id):
    try:
        booking = venue_service.cancel_booking(booking_id, g.current_user["id"], g.current_profile["role"] == "admin")
        if not booking:
            return error("NOT_FOUND", "Booking not found", 404)
        return success(booking)
    except venue_service.VenueServiceError as exc:
        return _handle_service_error(exc)
    except DatabaseError:
        return error("DATABASE_ERROR", "The booking could not be cancelled", 500)


@venues_management_bp.post("/manage")
@require_auth
@require_role("admin")
def create_venue():
    try:
        return success(venue_service.create_venue(request.get_json(silent=True)), 201)
    except venue_service.VenueServiceError as exc:
        return _handle_service_error(exc)
    except UniqueViolation:
        return error("VENUE_EXISTS", "A venue with this name already exists", 409)
    except DatabaseError:
        return error("DATABASE_ERROR", "The venue could not be created", 500)


@venues_management_bp.patch("/manage/<venue_id>")
@require_auth
@require_role("admin")
def update_venue(venue_id):
    try:
        venue = venue_service.update_venue(venue_id, request.get_json(silent=True))
        return success(venue) if venue else error("NOT_FOUND", "Venue not found", 404)
    except venue_service.VenueServiceError as exc:
        return _handle_service_error(exc)
    except UniqueViolation:
        return error("VENUE_EXISTS", "A venue with this name already exists", 409)
    except DatabaseError:
        return error("DATABASE_ERROR", "The venue could not be updated", 500)
