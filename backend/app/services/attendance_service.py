"""Secure event-pass and attendance operations."""

import base64
import hashlib
import hmac
import io
import json
from datetime import datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import qrcode
from flask import current_app
from psycopg.errors import UniqueViolation

from app.db import get_connection


class AttendanceError(Exception):
    def __init__(self, code, message, status=409):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def _uuid(value, field):
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError):
        raise AttendanceError("INVALID_ID", f"{field} must be a valid UUID", 422)


def _json_value(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    return value


def _secret():
    value = current_app.config.get("ATTENDANCE_QR_SECRET", "")
    if not value:
        raise AttendanceError("CONFIGURATION_ERROR", "Attendance QR signing is not configured", 500)
    return value.encode("utf-8")


def _canonical(registration_id):
    return json.dumps(
        {"registration_id": str(registration_id), "type": "eventsphere_attendance"},
        separators=(",", ":"),
        sort_keys=True,
    )


def _signed_payload(registration_id):
    canonical = _canonical(registration_id)
    signature = hmac.new(_secret(), canonical.encode("utf-8"), hashlib.sha256).hexdigest()
    document = {"registration_id": str(registration_id), "token": signature, "type": "eventsphere_attendance"}
    return json.dumps(document, separators=(",", ":"), sort_keys=True)


def _qr_image_data_url(payload):
    """Render the signed attendance payload as a browser-displayable PNG."""

    image = qrcode.make(payload)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _verify_payload(raw_payload):
    if not isinstance(raw_payload, str) or len(raw_payload) > 4096:
        raise AttendanceError("MALFORMED_QR", "QR payload is malformed", 400)
    try:
        payload = json.loads(raw_payload)
        registration_id = _uuid(payload.get("registration_id"), "registration_id")
        token = payload.get("token")
    except (json.JSONDecodeError, TypeError, AttributeError):
        raise AttendanceError("MALFORMED_QR", "QR payload is malformed", 400)
    if payload.get("type") != "eventsphere_attendance" or not isinstance(token, str):
        raise AttendanceError("INVALID_QR", "QR payload is not a valid EventSphere pass", 400)
    expected = hmac.new(_secret(), _canonical(registration_id).encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(token, expected):
        raise AttendanceError("INVALID_QR", "QR signature is invalid", 400)
    return registration_id


def _window_is_open(event_date, start_time, end_time):
    try:
        timezone = ZoneInfo(current_app.config.get("ATTENDANCE_TIMEZONE", "Asia/Kolkata"))
    except ZoneInfoNotFoundError:
        raise AttendanceError("CONFIGURATION_ERROR", "Attendance timezone is invalid", 500)
    now = datetime.now(timezone)
    start = datetime.combine(event_date, start_time, tzinfo=timezone) - timedelta(
        minutes=int(current_app.config.get("ATTENDANCE_EARLY_MINUTES", 30))
    )
    end = datetime.combine(event_date, end_time, tzinfo=timezone) + timedelta(
        minutes=int(current_app.config.get("ATTENDANCE_LATE_MINUTES", 120))
    )
    return start <= now <= end


def get_event_pass(registration_id, student_id):
    registration_id = _uuid(registration_id, "registration_id")
    student_id = _uuid(student_id, "student_id")
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """select r.id, r.status, r.student_id, e.id, e.title, e.description,
                          e.event_date, e.start_time, e.end_time, e.status,
                          v.name, v.location, p.full_name, p.department, p.year,
                          a.status, a.checked_in_at, r.participation_type, t.id, t.name,
                          coalesce((select jsonb_agg(jsonb_build_object('full_name', tm.full_name, 'email', tm.email, 'position', tm.position) order by tm.position)
                                    from team_members tm where tm.team_id = r.team_id), '[]'::jsonb)
                   from registrations r
                   join events e on e.id = r.event_id
                   join venues v on v.id = e.venue_id
                   join profiles p on p.id = r.student_id
                   left join teams t on t.id = r.team_id
                   left join attendance a on a.registration_id = r.id
                   where r.id = %s and (r.student_id = %s or exists (select 1 from team_members tm where tm.team_id = r.team_id and tm.student_id = %s))""",
                (registration_id, student_id, student_id),
            )
            row = cursor.fetchone()
            if not row:
                raise AttendanceError("PASS_NOT_FOUND", "Event pass not found", 404)
            if row[1] != "registered" or row[9] != "published":
                raise AttendanceError("PASS_UNAVAILABLE", "Event pass is unavailable for this registration", 409)
            qr_payload = _signed_payload(registration_id)
            return {
                "registration_id": str(row[0]),
                "registration_status": row[1],
                "event": {
                    "id": str(row[3]), "title": row[4], "description": row[5],
                    "event_date": _json_value(row[6]), "start_time": _json_value(row[7]),
                    "end_time": _json_value(row[8]), "status": row[9],
                    "venue": {"name": row[10], "location": row[11]},
                },
                "student": {"name": row[12], "department": row[13], "year": row[14]},
                "attendance": {"status": row[15] or "not_checked_in", "checked_in_at": _json_value(row[16])},
                "participation_type": row[17],
                "team": {"id": str(row[18]), "name": row[19], "members": row[20] or []} if row[17] == "team" else None,
                "qr_payload": qr_payload,
                "qr_image": _qr_image_data_url(qr_payload),
            }


def check_in(raw_payload, scanner_id, scanner_role):
    registration_id = _verify_payload(raw_payload)
    scanner_id = _uuid(scanner_id, "scanner_id")
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """select r.id, r.status, r.student_id, e.id, e.organizer_id,
                          e.title, e.event_date, e.start_time, e.end_time, e.status
                   from registrations r join events e on e.id = r.event_id
                   where r.id = %s for update""",
                (registration_id,),
            )
            row = cursor.fetchone()
            if not row:
                raise AttendanceError("REGISTRATION_NOT_FOUND", "Registration not found", 404)
            if row[1] != "registered":
                raise AttendanceError("REGISTRATION_INACTIVE", "Registration is not active", 409)
            if row[9] != "published":
                raise AttendanceError("EVENT_UNAVAILABLE", "Event is not available for attendance", 409)
            if scanner_role == "organizer" and str(row[4]) != str(scanner_id):
                raise AttendanceError("FORBIDDEN", "You do not own this event", 403)
            if not _window_is_open(row[6], row[7], row[8]):
                raise AttendanceError("ATTENDANCE_CLOSED", "Attendance is outside the event check-in window", 409)
            cursor.execute("select id from attendance where registration_id = %s for update", (registration_id,))
            if cursor.fetchone():
                raise AttendanceError("ALREADY_CHECKED_IN", "This registration is already checked in", 409)
            try:
                cursor.execute(
                    """insert into attendance (registration_id, event_id, student_id, scanned_by, status)
                       values (%s, %s, %s, %s, 'present')
                       returning id, checked_in_at, status""",
                    (registration_id, row[3], row[2], scanner_id),
                )
            except UniqueViolation:
                raise AttendanceError("ALREADY_CHECKED_IN", "This registration is already checked in", 409)
            attendance_id, checked_in_at, status = cursor.fetchone()
            return {"attendance_id": str(attendance_id), "registration_id": str(registration_id),
                    "event_id": str(row[3]), "status": status, "checked_in_at": _json_value(checked_in_at)}


def list_event_attendance(event_id):
    event_id = _uuid(event_id, "event_id")
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("select id, title, event_date, start_time, end_time, status from events where id = %s", (event_id,))
            event = cursor.fetchone()
            if not event:
                raise AttendanceError("EVENT_NOT_FOUND", "Event not found", 404)
            cursor.execute(
                """select r.id, r.status, p.full_name, p.email, p.department, p.year,
                          a.status, a.checked_in_at, r.participation_type, t.name,
                          coalesce((select jsonb_agg(jsonb_build_object('full_name', tm.full_name, 'email', tm.email) order by tm.position)
                                    from team_members tm where tm.team_id=r.team_id), '[]'::jsonb)
                   from registrations r join profiles p on p.id = r.student_id
                   left join teams t on t.id = r.team_id
                   left join attendance a on a.registration_id = r.id
                   where r.event_id = %s order by p.full_name asc""",
                (event_id,),
            )
            attendees = []
            for row in cursor.fetchall():
                attendees.append({"registration_id": str(row[0]), "registration_status": row[1],
                                  "student": {"name": row[2], "email": row[3], "department": row[4], "year": row[5]},
                                  "attendance_status": row[6] or "absent", "checked_in_at": _json_value(row[7]),
                                  "participation_type": row[8], "team": {"name": row[9], "members": row[10] or []} if row[8] == "team" else None})
            registered = sum(1 for attendee in attendees if attendee["registration_status"] == "registered")
            checked_in = sum(1 for attendee in attendees if attendee["registration_status"] == "registered" and attendee["attendance_status"] == "present")
            return {"event": {"id": str(event[0]), "title": event[1], "event_date": _json_value(event[2]),
                               "start_time": _json_value(event[3]), "end_time": _json_value(event[4]), "status": event[5]},
                    "summary": {"registered": registered, "checked_in": checked_in, "absent": registered - checked_in,
                                 "attendance_percentage": round((checked_in / registered) * 100, 2) if registered else 0},
                    "attendees": attendees}
