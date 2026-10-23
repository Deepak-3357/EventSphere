"""Transactional registration operations and participant queries."""

from datetime import datetime, timezone
import re
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
                  registration_deadline, status, participation_mode,
                  min_team_size, max_team_size
           from events where id = %s for update""",
        (event_id,),
    )
    return cursor.fetchone()


def _check_event_eligibility(event):
    if not event:
        raise RegistrationError("EVENT_NOT_FOUND", "Event not found", 404)
    event_id, title, event_date, start_time, end_time, capacity, deadline, status, mode, min_size, max_size = event
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
        "participation_mode": mode,
        "min_team_size": min_size,
        "max_team_size": max_size,
    }


def _clean_member(member, index):
    if not isinstance(member, dict):
        raise RegistrationError("INVALID_TEAM_MEMBER", f"Team member {index + 1} must be an object", 422)
    name = member.get("full_name")
    email = member.get("email")
    department = member.get("department") or None
    year = member.get("year")
    if not isinstance(name, str) or not 2 <= len(name.strip()) <= 160:
        raise RegistrationError("INVALID_TEAM_MEMBER", f"Team member {index + 1} has an invalid name", 422)
    if not isinstance(email, str) or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email.strip()):
        raise RegistrationError("INVALID_TEAM_MEMBER", f"Team member {index + 1} has an invalid email", 422)
    if year is not None and (isinstance(year, bool) or not isinstance(year, int) or not 1 <= year <= 8):
        raise RegistrationError("INVALID_TEAM_MEMBER", f"Team member {index + 1} has an invalid year", 422)
    return {"full_name": name.strip(), "email": email.strip().lower(), "department": department, "year": year}


def _team_input(cursor, event, student_id, payload):
    participation_type = payload.get("participation_type", "individual") if isinstance(payload, dict) else "individual"
    if participation_type not in {"individual", "team"}:
        raise RegistrationError("INVALID_PARTICIPATION_TYPE", "participation_type must be individual or team", 422)
    if participation_type == "individual":
        if event["participation_mode"] not in {"individual", "both"}:
            raise RegistrationError("PARTICIPATION_NOT_ALLOWED", "This event accepts team registrations only")
        return participation_type, None, []
    if event["participation_mode"] not in {"team", "both"}:
        raise RegistrationError("PARTICIPATION_NOT_ALLOWED", "This event accepts individual registrations only")
    team = payload.get("team") if isinstance(payload, dict) else None
    if not isinstance(team, dict) or not isinstance(team.get("name"), str) or not 2 <= len(team.get("name", "").strip()) <= 120:
        raise RegistrationError("INVALID_TEAM", "Team name and members are required", 422)
    members = team.get("members")
    if not isinstance(members, list):
        raise RegistrationError("INVALID_TEAM", "Team members must be an array", 422)
    cleaned = [_clean_member(member, index) for index, member in enumerate(members)]
    cursor.execute("select full_name, email, department, year from profiles where id=%s", (student_id,))
    leader = cursor.fetchone()
    if not leader:
        raise RegistrationError("PROFILE_NOT_FOUND", "Your student profile could not be loaded", 403)
    all_members = [{"full_name": leader[0], "email": leader[1].lower(), "department": leader[2], "year": leader[3]}] + cleaned
    emails = [member["email"] for member in all_members]
    if len(set(emails)) != len(emails):
        raise RegistrationError("DUPLICATE_TEAM_MEMBER", "Team member emails must be unique", 422)
    if not event["min_team_size"] <= len(all_members) <= event["max_team_size"]:
        raise RegistrationError("INVALID_TEAM_SIZE", f"Team size must be between {event['min_team_size']} and {event['max_team_size']} members", 422)
    return participation_type, team["name"].strip(), all_members


def register_student(event_id, student_id, payload=None):
    event_id = parse_uuid(event_id, "event_id")
    student_id = parse_uuid(student_id, "student_id")
    payload = payload or {}
    with get_connection() as connection:
        with connection.cursor() as cursor:
            event = _check_event_eligibility(_event_for_registration(cursor, event_id))
            participation_type, team_name, members = _team_input(cursor, event, student_id, payload)

            cursor.execute(
                """select id, status, participation_type, team_id from registrations
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
                if existing[2] != participation_type:
                    raise RegistrationError("REGISTRATION_TYPE_CONFLICT", "Cancel the previous registration before changing participation type")
                team_id = existing[3]
                if participation_type == "team":
                    cursor.execute("update teams set name=%s, updated_at=now() where id=%s", (team_name, team_id))
                    cursor.execute("delete from team_members where team_id=%s", (team_id,))
                    _insert_team_members(cursor, team_id, members, student_id)
                cursor.execute(
                    """update registrations set status = 'registered', registered_at = now()
                       where id = %s returning id, event_id, student_id, registered_at, status, participation_type, team_id""",
                    (existing[0],),
                )
                row = cursor.fetchone()
                columns = [description.name for description in cursor.description]
            else:
                team_id = None
                if participation_type == "team":
                    cursor.execute("insert into teams(event_id, name, leader_id) values(%s,%s,%s) returning id", (event_id, team_name, student_id))
                    team_id = cursor.fetchone()[0]
                cursor.execute(
                    """insert into registrations (event_id, student_id, status, participation_type, team_id)
                       values (%s, %s, 'registered', %s, %s)
                       returning id, event_id, student_id, registered_at, status, participation_type, team_id""",
                    (event_id, student_id, participation_type, team_id),
                )
                row = cursor.fetchone()
                columns = [description.name for description in cursor.description]
                if team_id:
                    _insert_team_members(cursor, team_id, members, student_id)
            notification_service.create_notification(
                cursor,
                student_id,
                "Registration Confirmed",
                f"You have successfully registered for {event['title']}.",
                "registration",
            )
            return _registration_from_row(row, columns)


def _insert_team_members(cursor, team_id, members, leader_id):
    for position, member in enumerate(members):
        cursor.execute("select id from profiles where lower(email)=lower(%s)", (member["email"],))
        profile = cursor.fetchone()
        member_id = profile[0] if profile else None
        if member_id and str(member_id) != str(leader_id):
            cursor.execute("""select 1 from team_members tm join registrations r on r.team_id=tm.team_id
                              where r.event_id=(select event_id from teams where id=%s)
                                and r.status='registered' and tm.student_id=%s limit 1""", (team_id, member_id))
            if cursor.fetchone():
                raise RegistrationError("DUPLICATE_MEMBER_REGISTRATION", "A team member already has an active registration for this event")
        cursor.execute("""insert into team_members(team_id, student_id, full_name, email, department, year, position)
                          values(%s,%s,%s,%s,%s,%s,%s)""", (team_id, member_id, member["full_name"], member["email"], member["department"], member["year"], position))


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
        r.participation_type, r.team_id, t.name as team_name,
        coalesce((select jsonb_agg(jsonb_build_object(
            'id', tm.id, 'student_id', tm.student_id, 'full_name', tm.full_name,
            'email', tm.email, 'department', tm.department, 'year', tm.year,
            'position', tm.position) order by tm.position)
            from team_members tm where tm.team_id = r.team_id), '[]'::jsonb) as team_members,
        e.title, e.event_date, e.start_time, e.end_time, e.capacity,
        e.registration_deadline, e.status as event_status,
        v.name as venue_name, v.location as venue_location,
        c.name as category_name,
        p.full_name as student_name, p.department as student_department, p.year as student_year
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
    data["team"] = None
    if data.pop("participation_type") == "team":
        data["team"] = {"id": data.pop("team_id"), "name": data.pop("team_name"), "members": data.pop("team_members") or []}
    else:
        data.pop("team_id")
        data.pop("team_name")
        data.pop("team_members")
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
                    left join teams t on t.id = r.team_id
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
                    left join teams t on t.id = r.team_id
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
                    left join teams t on t.id = r.team_id
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
                    left join teams t on t.id = r.team_id{where}
                    order by r.registered_at desc""",
                params,
            )
            columns = [description.name for description in cursor.description]
            return [_serialize_registration(row, columns) for row in cursor.fetchall()]


def get_event_pass(registration_id, student_id):
    registration_id = parse_uuid(registration_id, "registration_id")
    student_id = parse_uuid(student_id, "student_id")
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """select r.id, r.status, r.student_id, e.id, e.title, e.description,
                          e.event_date, e.start_time, e.end_time, e.status,
                          v.name, v.location, p.full_name, p.department, p.year,
                          r.participation_type, t.id, t.name,
                          coalesce((select jsonb_agg(jsonb_build_object('full_name', tm.full_name, 'email', tm.email, 'position', tm.position) order by tm.position)
                                    from team_members tm where tm.team_id = r.team_id), '[]'::jsonb),
                          r.registered_at
                   from registrations r
                   join events e on e.id = r.event_id
                   join venues v on v.id = e.venue_id
                   join profiles p on p.id = r.student_id
                   left join teams t on t.id = r.team_id
                   where r.id = %s and (r.student_id = %s or exists (select 1 from team_members tm where tm.team_id = r.team_id and tm.student_id = %s))""",
                (registration_id, student_id, student_id),
            )
            row = cursor.fetchone()
            if not row:
                raise RegistrationError("PASS_NOT_FOUND", "Event pass not found", 404)
            if row[1] != "registered" or row[9] != "published":
                raise RegistrationError("PASS_UNAVAILABLE", "Event pass is unavailable for this registration", 409)
            return {
                "registration_id": str(row[0]),
                "registration_status": row[1],
                "registered_at": row[19].isoformat() if hasattr(row[19], "isoformat") else str(row[19]),
                "event": {
                    "id": str(row[3]),
                    "title": row[4],
                    "description": row[5],
                    "event_date": row[6].isoformat() if hasattr(row[6], "isoformat") else str(row[6]),
                    "start_time": row[7].isoformat() if hasattr(row[7], "isoformat") else str(row[7]),
                    "end_time": row[8].isoformat() if hasattr(row[8], "isoformat") else str(row[8]),
                    "status": row[9],
                    "venue": {"name": row[10], "location": row[11]},
                },
                "student": {"name": row[12], "department": row[13], "year": row[14]},
                "participation_type": row[15],
                "team": {"id": str(row[16]), "name": row[17], "members": row[18] or []} if row[15] == "team" else None,
            }
