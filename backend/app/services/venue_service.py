"""Venue availability and booking operations.

All booking times are accepted as campus-local Asia/Kolkata date/time values
and stored as timestamptz. Database row locks plus the exclusion constraint
protect the final booking write from concurrent submissions.
"""

from datetime import date, datetime, time
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from app.db import get_connection


CAMPUS_TIMEZONE = ZoneInfo("Asia/Kolkata")
ACTIVE_EVENT_STATUSES = ("draft", "pending", "published")
BOOKING_STATUSES = {"confirmed", "cancelled"}


class VenueServiceError(ValueError):
    def __init__(self, code: str, message: str, status: int = 422):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


def parse_uuid(value: Any, field: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError):
        raise VenueServiceError("VALIDATION_ERROR", f"{field} must be a valid UUID")


def parse_slot(payload: dict[str, Any]) -> tuple[datetime, datetime, date]:
    event_date = payload.get("date")
    start_value = payload.get("start_time")
    end_value = payload.get("end_time")
    try:
        parsed_date = date.fromisoformat(event_date)
        start = time.fromisoformat(start_value)
        end = time.fromisoformat(end_value)
    except (TypeError, ValueError):
        raise VenueServiceError("VALIDATION_ERROR", "date must use YYYY-MM-DD and times must use HH:MM format")
    if end <= start:
        raise VenueServiceError("VALIDATION_ERROR", "end_time must be later than start_time; overnight bookings are not supported")
    start_at = datetime.combine(parsed_date, start, tzinfo=CAMPUS_TIMEZONE)
    end_at = datetime.combine(parsed_date, end, tzinfo=CAMPUS_TIMEZONE)
    return start_at, end_at, parsed_date


def _serialize_venue(row):
    return {"id": str(row[0]), "name": row[1], "location": row[2], "capacity": row[3], "is_active": row[4]}


def list_venues(include_inactive=False):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "select id, name, location, capacity, is_active from venues "
                + ("" if include_inactive else "where is_active = true ")
                + "order by name"
            )
            return [_serialize_venue(row) for row in cursor.fetchall()]


def get_venue(cursor, venue_id: str, lock=False):
    cursor.execute(
        "select id, name, location, capacity, is_active from venues where id = %s" + (" for update" if lock else ""),
        (venue_id,),
    )
    row = cursor.fetchone()
    return _serialize_venue(row) if row else None


def _event_conflict(cursor, venue_id, start_at, end_at, exclude_event_id=None):
    params = [venue_id, start_at, end_at]
    exclusion = ""
    if exclude_event_id:
        exclusion = " and id <> %s"
        params.append(exclude_event_id)
    cursor.execute(
        """select id, title, event_date, start_time, end_time from events
           where venue_id = %s and status = any(%s)
             and ((event_date + start_time) at time zone 'Asia/Kolkata') < %s
             and ((event_date + end_time) at time zone 'Asia/Kolkata') > %s""" + exclusion,
        [venue_id, list(ACTIVE_EVENT_STATUSES), end_at, start_at] + ([exclude_event_id] if exclude_event_id else []),
    )
    return cursor.fetchone()


def _booking_conflict(cursor, venue_id, start_at, end_at, exclude_booking_id=None):
    params = [venue_id, end_at, start_at]
    exclusion = ""
    if exclude_booking_id:
        exclusion = " and id <> %s"
        params.append(exclude_booking_id)
    cursor.execute(
        """select id, title, start_at, end_at from venue_bookings
           where venue_id = %s and status = 'confirmed'
             and start_at < %s and end_at > %s""" + exclusion,
        params,
    )
    return cursor.fetchone()


def ensure_event_slot_available(cursor, venue_id, start_at, end_at, event_id=None):
    """Lock the venue and reject event/booking conflicts before event writes."""

    venue = get_venue(cursor, parse_uuid(venue_id, "venue_id"), lock=True)
    if not venue:
        raise VenueServiceError("NOT_FOUND", "Venue does not exist", 404)
    if not venue["is_active"]:
        raise VenueServiceError("VENUE_INACTIVE", "This venue is not accepting event reservations", 409)
    if _event_conflict(cursor, venue["id"], start_at, end_at, event_id) or _booking_conflict(cursor, venue["id"], start_at, end_at):
        raise VenueServiceError("VENUE_CONFLICT", "The venue is reserved during this time", 409)
    return venue


def _conflict_details(row, kind):
    if not row:
        return None
    if kind == "event":
        return {"type": "event", "id": str(row[0]), "title": row[1], "date": str(row[2]), "start_time": str(row[3]), "end_time": str(row[4])}
    return {"type": "booking", "id": str(row[0]), "title": row[1]}


def availability(venue_id, requested_date, include_details=False):
    venue_id = parse_uuid(venue_id, "venue_id")
    try:
        selected_date = date.fromisoformat(requested_date)
    except (TypeError, ValueError):
        raise VenueServiceError("VALIDATION_ERROR", "date must use YYYY-MM-DD format")
    day_start = datetime.combine(selected_date, time.min, tzinfo=CAMPUS_TIMEZONE)
    day_end = datetime.combine(selected_date, time.max, tzinfo=CAMPUS_TIMEZONE)
    with get_connection() as connection:
        with connection.cursor() as cursor:
            venue = get_venue(cursor, venue_id)
            if not venue:
                raise VenueServiceError("NOT_FOUND", "Venue not found", 404)
            if include_details:
                cursor.execute(
                    """select id, title, start_at, end_at from venue_bookings
                       where venue_id = %s and status = 'confirmed' and start_at < %s and end_at > %s
                       order by start_at""",
                    (venue_id, day_end, day_start),
                )
                bookings = [{"id": str(row[0]), "title": row[1], "start_at": row[2].isoformat(), "end_at": row[3].isoformat()} for row in cursor.fetchall()]
                cursor.execute(
                    """select id, title, event_date, start_time, end_time, status from events
                       where venue_id = %s and status = any(%s)
                         and event_date = %s order by start_time""",
                    (venue_id, list(ACTIVE_EVENT_STATUSES), selected_date),
                )
                events = [{"id": str(row[0]), "title": row[1], "date": str(row[2]), "start_time": str(row[3]), "end_time": str(row[4]), "status": row[5]} for row in cursor.fetchall()]
            else:
                cursor.execute(
                    """select start_at, end_at from venue_bookings
                       where venue_id = %s and status = 'confirmed' and start_at < %s and end_at > %s
                       order by start_at""",
                    (venue_id, day_end, day_start),
                )
                bookings = [{"start_at": row[0].isoformat(), "end_at": row[1].isoformat()} for row in cursor.fetchall()]
                cursor.execute(
                    """select event_date, start_time, end_time from events
                       where venue_id = %s and status = any(%s)
                         and event_date = %s order by start_time""",
                    (venue_id, list(ACTIVE_EVENT_STATUSES), selected_date),
                )
                events = [{"date": str(row[0]), "start_time": str(row[1]), "end_time": str(row[2])} for row in cursor.fetchall()]
            return {"venue": venue, "date": selected_date.isoformat(), "bookings": bookings, "events": events}


def restricted_availability(payload):
    if not isinstance(payload, dict):
        raise VenueServiceError("VALIDATION_ERROR", "Request body must be a JSON object")
    start_at, end_at, _ = parse_slot(payload)
    venue_id = parse_uuid(payload.get("venue_id"), "venue_id")
    with get_connection() as connection:
        with connection.cursor() as cursor:
            venue = get_venue(cursor, venue_id)
            if not venue:
                raise VenueServiceError("NOT_FOUND", "Venue not found", 404)
            if not venue["is_active"]:
                return {"available": False, "reason": "venue_inactive"}
            event = _event_conflict(cursor, venue_id, start_at, end_at)
            booking = _booking_conflict(cursor, venue_id, start_at, end_at)
            return {"available": not event and not booking, "reason": "available" if not event and not booking else "slot_occupied"}


def create_booking(payload, requester_id, role):
    if not isinstance(payload, dict):
        raise VenueServiceError("VALIDATION_ERROR", "Request body must be a JSON object")
    title = payload.get("title") or payload.get("purpose")
    if not isinstance(title, str) or not 1 <= len(title.strip()) <= 200:
        raise VenueServiceError("VALIDATION_ERROR", "title must be between 1 and 200 characters")
    venue_id = parse_uuid(payload.get("venue_id"), "venue_id")
    event_id = parse_uuid(payload["event_id"], "event_id") if payload.get("event_id") else None
    start_at, end_at, selected_date = parse_slot(payload)
    with get_connection() as connection:
        with connection.cursor() as cursor:
            venue = get_venue(cursor, venue_id, lock=True)
            if not venue:
                raise VenueServiceError("NOT_FOUND", "Venue not found", 404)
            if not venue["is_active"]:
                raise VenueServiceError("VENUE_INACTIVE", "This venue is not accepting new bookings", 409)
            if event_id:
                cursor.execute("select organizer_id from events where id = %s", (event_id,))
                event = cursor.fetchone()
                if not event:
                    raise VenueServiceError("NOT_FOUND", "Linked event not found", 404)
                if role not in {"admin"} and str(event[0]) != str(requester_id):
                    raise VenueServiceError("FORBIDDEN", "You may only link your own event", 403)
            event_conflict = _event_conflict(cursor, venue_id, start_at, end_at, event_id)
            if event_conflict:
                raise VenueServiceError("VENUE_CONFLICT", "The venue is reserved by an event during this time", 409)
            booking_conflict = _booking_conflict(cursor, venue_id, start_at, end_at)
            if booking_conflict:
                raise VenueServiceError("VENUE_CONFLICT", "The venue is already booked during this time", 409)
            cursor.execute(
                """insert into venue_bookings (venue_id, requester_id, event_id, title, start_at, end_at)
                   values (%s, %s, %s, %s, %s, %s)
                   returning id, created_at""",
                (venue_id, requester_id, event_id, title.strip(), start_at, end_at),
            )
            row = cursor.fetchone()
            if not row:
                raise RuntimeError("Booking could not be created")
            return {"id": str(row[0]), "venue": venue, "title": title.strip(), "date": selected_date.isoformat(), "start_time": start_at.strftime("%H:%M"), "end_time": end_at.strftime("%H:%M"), "status": "confirmed", "created_at": row[1].isoformat()}


def list_bookings(requester_id=None, include_all=False):
    params = []
    where = ""
    if not include_all:
        where = "where b.requester_id = %s"
        params.append(requester_id)
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """select b.id, b.venue_id, v.name, b.requester_id, p.full_name, b.event_id,
                          b.title, b.start_at, b.end_at, b.status, b.created_at
                   from venue_bookings b join venues v on v.id = b.venue_id
                   join profiles p on p.id = b.requester_id """ + where + " order by b.start_at desc",
                params,
            )
            return [_serialize_booking(row) for row in cursor.fetchall()]


def _serialize_booking(row):
    return {"id": str(row[0]), "venue_id": str(row[1]), "venue_name": row[2], "requester_id": str(row[3]), "requester_name": row[4], "event_id": str(row[5]) if row[5] else None, "title": row[6], "start_at": row[7].isoformat(), "end_at": row[8].isoformat(), "status": row[9], "created_at": row[10].isoformat()}


def get_booking(booking_id):
    booking_id = parse_uuid(booking_id, "booking_id")
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """select b.id, b.venue_id, v.name, b.requester_id, p.full_name, b.event_id,
                          b.title, b.start_at, b.end_at, b.status, b.created_at
                   from venue_bookings b join venues v on v.id = b.venue_id
                   join profiles p on p.id = b.requester_id where b.id = %s""",
                (booking_id,),
            )
            row = cursor.fetchone()
            return _serialize_booking(row) if row else None


def cancel_booking(booking_id, requester_id, is_admin=False):
    booking_id = parse_uuid(booking_id, "booking_id")
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("select requester_id, status from venue_bookings where id = %s for update", (booking_id,))
            row = cursor.fetchone()
            if not row:
                return None
            if not is_admin and str(row[0]) != str(requester_id):
                raise VenueServiceError("FORBIDDEN", "You may only cancel your own booking", 403)
            if row[1] == "cancelled":
                cursor.execute(
                    """select b.id, b.venue_id, v.name, b.requester_id, p.full_name, b.event_id,
                              b.title, b.start_at, b.end_at, b.status, b.created_at
                       from venue_bookings b join venues v on v.id = b.venue_id
                       join profiles p on p.id = b.requester_id where b.id = %s""",
                    (booking_id,),
                )
                return _serialize_booking(cursor.fetchone())
            cursor.execute("update venue_bookings set status = 'cancelled', updated_at = now() where id = %s", (booking_id,))
            cursor.execute(
                """select b.id, b.venue_id, v.name, b.requester_id, p.full_name, b.event_id,
                          b.title, b.start_at, b.end_at, b.status, b.created_at
                   from venue_bookings b join venues v on v.id = b.venue_id
                   join profiles p on p.id = b.requester_id where b.id = %s""",
                (booking_id,),
            )
            return _serialize_booking(cursor.fetchone())


def create_venue(payload):
    if not isinstance(payload, dict):
        raise VenueServiceError("VALIDATION_ERROR", "Request body must be a JSON object")
    name, location, capacity = payload.get("name"), payload.get("location"), payload.get("capacity")
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 200 or not isinstance(location, str) or not 1 <= len(location.strip()) <= 300:
        raise VenueServiceError("VALIDATION_ERROR", "name and location are required")
    if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity <= 0:
        raise VenueServiceError("VALIDATION_ERROR", "capacity must be a positive integer")
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("insert into venues(name, location, capacity) values(%s,%s,%s) returning id, name, location, capacity, is_active", (name.strip(), location.strip(), capacity))
            return _serialize_venue(cursor.fetchone())


def update_venue(venue_id, payload):
    venue_id = parse_uuid(venue_id, "venue_id")
    if not isinstance(payload, dict):
        raise VenueServiceError("VALIDATION_ERROR", "Request body must be a JSON object")
    fields, params = [], []
    for key, limit in (("name", 200), ("location", 300)):
        if key in payload:
            value = payload[key]
            if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
                raise VenueServiceError("VALIDATION_ERROR", f"{key} is invalid")
            fields.append(f"{key} = %s"); params.append(value.strip())
    if "capacity" in payload:
        if isinstance(payload["capacity"], bool) or not isinstance(payload["capacity"], int) or payload["capacity"] <= 0:
            raise VenueServiceError("VALIDATION_ERROR", "capacity must be a positive integer")
        fields.append("capacity = %s"); params.append(payload["capacity"])
    if "is_active" in payload:
        if not isinstance(payload["is_active"], bool):
            raise VenueServiceError("VALIDATION_ERROR", "is_active must be boolean")
        fields.append("is_active = %s"); params.append(payload["is_active"])
    if not fields:
        raise VenueServiceError("VALIDATION_ERROR", "At least one venue field is required")
    params.append(venue_id)
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(f"update venues set {', '.join(fields)} where id = %s returning id, name, location, capacity, is_active", params)
            row = cursor.fetchone()
            return _serialize_venue(row) if row else None
