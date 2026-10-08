"""Transactional registration operations and participant queries."""

from datetime import datetime, timezone
from uuid import UUID

from app.db import get_connection
from app.services import notification_service


class RegistrationError(Exception):
    """A safe, client-facing registration business-rule failure."""

    def __init__(self, code, message, status=409):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def parse_uuid(value, field):
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError):
        raise RegistrationError("INVALID_ID", f"{field} must be a valid UUID", 422)


def _serialize(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    return value


def _registration_from_row(row, columns):
    return {column: _serialize(value) for column, value in zip(columns, row)}


def _event_for_registration(cursor, event_id):
    cursor.execute(
        """select id, title, event_date, start_time, end_time, capacity,
                  registration_deadline, status
           from events where id = %s for update""",
        (event_id,),
    )
    return cursor.fetchone()


def _check_event_eligibility(event):
    if not event:
        raise RegistrationError("EVENT_NOT_FOUND", "Event not found", 404)
    event_id, title, event_date, start_time, end_time, capacity, deadline, status = event
    if status != "published":
        if status in {"cancelled", "completed"}:
            raise RegistrationError("EVENT_UNAVAILABLE", "This event is no longer available for registration")
        raise RegistrationError("EVENT_NOT_OPEN", "Only published events accept registrations")
    if deadline <= datetime.now(timezone.utc):
        raise RegistrationError("REGISTRATION_CLOSED", "Registration deadline has passed")
    return {
        "id": event_id,
        "title": title,
        "event_date": event_date,
        "start_time": start_time,
        "end_time": end_time,
        "capacity": capacity,
        "registration_deadline": deadline,
        "status": status,
    }


def register_student(event_id, student_id):
    event_id = parse_uuid(event_id, "event_id")
    student_id = parse_uuid(student_id, "student_id")
    with get_connection() as connection:
        with connection.cursor() as cursor:
            event = _check_event_eligibility(_event_for_registration(cursor, event_id))

            cursor.execute(
                """select id, status from registrations
                   where event_id = %s and student_id = %s for update""",
                (event_id, student_id),
            )
            existing = cursor.fetchone()
            if existing and existing[1] == "registered":
                raise RegistrationError("ALREADY_REGISTERED", "You are already registered for this event")

            cursor.execute(
                "select count(*) from registrations where event_id = %s and status = 'registered'",
                (event_id,),
            )
            registered_count = cursor.fetchone()[0]
            if registered_count >= event["capacity"]:
                raise RegistrationError("EVENT_FULL", "This event has no available seats")

            if existing and existing[1] == "cancelled":
                cursor.execute(
                    """update registrations set status = 'registered', registered_at = now()
                       where id = %s returning id, event_id, student_id, registered_at, status""",
                    (existing[0],),
                )
            else:
                cursor.execute(
                    """insert into registrations (event_id, student_id, status)
                       values (%s, %s, 'registered')
                       returning id, event_id, student_id, registered_at, status""",
                    (event_id, student_id),
                )
            row = cursor.fetchone()
            columns = [description.name for description in cursor.description]
            notification_service.create_notification(
                cursor,
                student_id,
                "Registration Confirmed",
                f"You have successfully registered for {event['title']}.",
                "registration",
            )
            return _registration_from_row(row, columns)


def cancel_student_registration(event_id, student_id):
    event_id = parse_uuid(event_id, "event_id")
    student_id = parse_uuid(student_id, "student_id")
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """select r.id, r.status, e.title from registrations r
                   join events e on e.id = r.event_id
                   where r.event_id = %s and r.student_id = %s for update""",
                (event_id, student_id),
            )
            registration = cursor.fetchone()
            if not registration:
                raise RegistrationError("REGISTRATION_NOT_FOUND", "Registration not found", 404)
            if registration[1] == "cancelled":
                raise RegistrationError("REGISTRATION_NOT_ACTIVE", "Registration is already cancelled")
            cursor.execute(
                """update registrations set status = 'cancelled'
                   where id = %s returning event_id, status""",
                (registration[0],),
            )
            row = cursor.fetchone()
            notification_service.create_notification(
                cursor,
                student_id,
                "Registration Cancelled",
                f"Your registration for {registration[2]} has been cancelled.",
                "cancellation",
            )
            return {"event_id": str(row[0]), "status": row[1]}


def _registration_select():
    return """
        r.id as registration_id, r.event_id, r.student_id, r.registered_at, r.status,
        e.title, e.event_date, e.start_time, e.end_time, e.capacity,
        e.registration_deadline, e.status as event_status,
        v.name as venue_name, v.location as venue_location,
        c.name as category_name,
        p.full_name as student_name, p.department as student_department, p.year as student_year,
        a.status as attendance_status, a.checked_in_at
    """


def _serialize_registration(row, columns):
    data = _registration_from_row(row, columns)
    data["event"] = {
        "id": data.pop("event_id"),
        "title": data.pop("title"),
        "event_date": data.pop("event_date"),
        "start_time": data.pop("start_time"),
        "end_time": data.pop("end_time"),
        "capacity": data.pop("capacity"),
        "registration_deadline": data.pop("registration_deadline"),
        "status": data.pop("event_status"),
        "venue": {"name": data.pop("venue_name"), "location": data.pop("venue_location")},
        "category": data.pop("category_name"),
    }
    data["attendance"] = {
        "status": data.pop("attendance_status") or "not_checked_in",
        "checked_in_at": data.pop("checked_in_at"),
    }
    return data


def list_student_registrations(student_id, status=None, upcoming=False):
    student_id = parse_uuid(student_id, "student_id")
    conditions = ["r.student_id = %s"]
    params = [student_id]
    if status:
        if status not in {"registered", "cancelled"}:
            raise RegistrationError("INVALID_STATUS", "status must be registered or cancelled", 422)
        conditions.append("r.status = %s")
        params.append(status)
    if upcoming:
        conditions.append("e.event_date >= current_date")
    where = " and ".join(conditions)
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""select {_registration_select()}
                    from registrations r
                    join events e on e.id = r.event_id
                    join venues v on v.id = e.venue_id
                    join categories c on c.id = e.category_id
                    join profiles p on p.id = r.student_id
                    left join attendance a on a.registration_id = r.id
                    where {where}
                    order by e.event_date asc, e.start_time asc, r.registered_at desc""",
                params,
            )
            columns = [description.name for description in cursor.description]
            return [_serialize_registration(row, columns) for row in cursor.fetchall()]


def get_registration(registration_id):
    registration_id = parse_uuid(registration_id, "registration_id")
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""select {_registration_select()}
                    from registrations r
                    join events e on e.id = r.event_id
                    join venues v on v.id = e.venue_id
                    join categories c on c.id = e.category_id
                    join profiles p on p.id = r.student_id
                    left join attendance a on a.registration_id = r.id
                    where r.id = %s""",
                (registration_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            columns = [description.name for description in cursor.description]
            return _serialize_registration(row, columns)


def list_event_registrations(event_id, status=None):
    event_id = parse_uuid(event_id, "event_id")
    conditions = ["r.event_id = %s"]
    params = [event_id]
    if status:
        if status not in {"registered", "cancelled"}:
            raise RegistrationError("INVALID_STATUS", "status must be registered or cancelled", 422)
        conditions.append("r.status = %s")
        params.append(status)
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""select {_registration_select()}
                    from registrations r
                    join events e on e.id = r.event_id
                    join venues v on v.id = e.venue_id
                    join categories c on c.id = e.category_id
                    join profiles p on p.id = r.student_id
                    left join attendance a on a.registration_id = r.id
                    where {' and '.join(conditions)}
                    order by r.registered_at asc""",
                params,
            )
            columns = [description.name for description in cursor.description]
            return [_serialize_registration(row, columns) for row in cursor.fetchall()]


def list_all_registrations(event_id=None, status=None, student_id=None):
    conditions = []
    params = []
    if event_id:
        conditions.append("r.event_id = %s")
        params.append(parse_uuid(event_id, "event_id"))
    if student_id:
        conditions.append("r.student_id = %s")
        params.append(parse_uuid(student_id, "student_id"))
    if status:
        if status not in {"registered", "cancelled"}:
            raise RegistrationError("INVALID_STATUS", "status must be registered or cancelled", 422)
        conditions.append("r.status = %s")
        params.append(status)
    where = f" where {' and '.join(conditions)}" if conditions else ""
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""select {_registration_select()}
                    from registrations r
                    join events e on e.id = r.event_id
                    join venues v on v.id = e.venue_id
                    join categories c on c.id = e.category_id
                    join profiles p on p.id = r.student_id
                    left join attendance a on a.registration_id = r.id{where}
                    order by r.registered_at desc""",
                params,
            )
            columns = [description.name for description in cursor.description]
            return [_serialize_registration(row, columns) for row in cursor.fetchall()]
