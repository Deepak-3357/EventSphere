"""Database operations for EventSphere event management."""

from datetime import date, datetime, time
from urllib.parse import urlparse
from uuid import UUID

from app.db import get_connection
from app.services import notification_service
from psycopg.types.json import Jsonb


EVENT_STATUSES = {"draft", "pending", "published", "cancelled", "completed"}
CREATE_STATUSES = {"draft", "pending"}
STATUS_TRANSITIONS = {
    "draft": {"pending", "published", "cancelled"},
    "pending": {"draft", "published", "cancelled"},
    "published": {"completed", "cancelled"},
    "cancelled": set(),
    "completed": set(),
}


def parse_uuid(value, field):
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError):
        raise ValueError(f"{field} must be a valid UUID")


def parse_date(value):
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError("event_date must use YYYY-MM-DD format")


def parse_time(value, field):
    if isinstance(value, time):
        return value
    try:
        return time.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field} must use HH:MM format")


def parse_deadline(value):
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value.strip():
        raise ValueError("registration_deadline is required")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("registration_deadline must be a valid ISO date/time")


def validate_image_url(value):
    if value in (None, ""):
        return None
    if not isinstance(value, str) or len(value) > 2048:
        raise ValueError("image_url must be a valid HTTP(S) URL")
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("image_url must be a valid HTTP(S) URL")
    return value


def validate_participation(payload):
    mode = payload.get("participation_mode", "individual")
    if mode not in {"individual", "team", "both"}:
        raise ValueError("participation_mode must be individual, team, or both")
    minimum = payload.get("min_team_size")
    maximum = payload.get("max_team_size")
    if mode == "individual":
        if minimum is not None or maximum is not None:
            raise ValueError("team size limits are only valid for team participation")
        return mode, None, None
    if any(isinstance(value, bool) or not isinstance(value, int) for value in (minimum, maximum)):
        raise ValueError("min_team_size and max_team_size are required integers for team participation")
    if minimum < 2 or maximum < minimum or maximum > 100:
        raise ValueError("team size must be between 2 and 100, with max_team_size >= min_team_size")
    return mode, minimum, maximum


def validate_event_payload(payload, current=None, requested_status=None):
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object")

    merged = dict(current or {})
    merged.update({key: value for key, value in payload.items() if key != "organizer_id"})
    required = ("title", "category_id", "venue_id", "event_date", "start_time", "end_time", "capacity", "registration_deadline")
    missing = [field for field in required if merged.get(field) in (None, "")]
    if missing:
        raise ValueError(f"Missing required field: {missing[0]}")

    title = merged["title"]
    if not isinstance(title, str) or not title.strip() or len(title.strip()) > 200:
        raise ValueError("title is required and must be 1-200 characters")

    description = merged.get("description") or ""
    if not isinstance(description, str) or len(description) > 5000:
        raise ValueError("description must be at most 5000 characters")

    category_id = parse_uuid(merged["category_id"], "category_id")
    venue_id = parse_uuid(merged["venue_id"], "venue_id")
    event_date = parse_date(merged["event_date"])
    start_time = parse_time(merged["start_time"], "start_time")
    end_time = parse_time(merged["end_time"], "end_time")
    if end_time <= start_time:
        raise ValueError("end_time must be after start_time")

    capacity = merged["capacity"]
    if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity <= 0:
        raise ValueError("capacity must be a positive integer")

    deadline = parse_deadline(merged["registration_deadline"])
    event_start = datetime.combine(event_date, start_time)
    if deadline.tzinfo is not None:
        deadline_for_compare = deadline.replace(tzinfo=None)
    else:
        deadline_for_compare = deadline
    if deadline_for_compare >= event_start:
        raise ValueError("registration_deadline must be before the event start")

    status = requested_status if requested_status is not None else merged.get("status", "draft")
    if status not in EVENT_STATUSES:
        raise ValueError("status must be one of draft, pending, published, cancelled, completed")

    participation_mode, min_team_size, max_team_size = validate_participation(merged)
    eligibility = merged.get("eligibility") or ""
    instructions = merged.get("registration_instructions") or ""
    if not isinstance(eligibility, str) or len(eligibility) > 2000:
        raise ValueError("eligibility must be at most 2000 characters")
    if not isinstance(instructions, str) or len(instructions) > 3000:
        raise ValueError("registration_instructions must be at most 3000 characters")
    facilities = merged.get("facilities") or {}
    if not isinstance(facilities, dict):
        raise ValueError("facilities must be a JSON object")
    if len(str(facilities)) > 5000:
        raise ValueError("facilities are too large")
    return {
        "title": title.strip(),
        "description": description.strip(),
        "category_id": category_id,
        "venue_id": venue_id,
        "event_date": event_date,
        "start_time": start_time,
        "end_time": end_time,
        "capacity": capacity,
        "registration_deadline": deadline,
        "status": status,
        "image_url": validate_image_url(merged.get("image_url")),
        "participation_mode": participation_mode,
        "min_team_size": min_team_size,
        "max_team_size": max_team_size,
        "eligibility": eligibility.strip(),
        "registration_instructions": instructions.strip(),
        "facilities": facilities,
    }


EVENT_SELECT = """
    e.id, e.title, e.description, e.category_id, e.organizer_id, e.venue_id,
    e.event_date, e.start_time, e.end_time, e.capacity,
    e.registration_deadline, e.status, e.image_url, e.participation_mode,
    e.min_team_size, e.max_team_size, e.eligibility, e.registration_instructions,
    e.facilities, e.created_at, e.updated_at,
    (select count(*) from registrations r where r.event_id = e.id and r.status = 'registered')::int as registered_count,
    (e.capacity - (select count(*) from registrations r where r.event_id = e.id and r.status = 'registered'))::int as available_seats,
    c.name as category_name,
    v.name as venue_name, v.location as venue_location, v.capacity as venue_capacity,
    p.full_name as organizer_name
"""


def _serialize(value):
    if isinstance(value, (date, time, datetime)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    return value


def serialize_event(row, columns):
    event = {column: _serialize(value) for column, value in zip(columns, row)}
    event["category"] = {"id": event.pop("category_id"), "name": event.pop("category_name")}
    event["venue"] = {
        "id": event.pop("venue_id"),
        "name": event.pop("venue_name"),
        "location": event.pop("venue_location"),
        "capacity": event.pop("venue_capacity"),
    }
    event["organizer"] = {"id": event.pop("organizer_id"), "name": event.pop("organizer_name")}
    return event


def _fetch_event(cursor, event_id):
    cursor.execute(
        f"""select {EVENT_SELECT}
            from events e
            join categories c on c.id = e.category_id
            join venues v on v.id = e.venue_id
            join profiles p on p.id = e.organizer_id
            where e.id = %s""",
        (event_id,),
    )
    row = cursor.fetchone()
    if not row:
        return None
    columns = [description.name for description in cursor.description]
    return serialize_event(row, columns)


def list_events(filters, role=None, user_id=None):
    page = filters["page"]
    limit = filters["limit"]
    conditions = []
    params = []
    if role == "admin":
        if filters.get("status"):
            conditions.append("e.status = %s")
            params.append(filters["status"])
    elif role == "organizer":
        conditions.append("(e.status = 'published' or e.organizer_id = %s)")
        params.append(user_id)
        if filters.get("status"):
            conditions.append("e.status = %s")
            params.append(filters["status"])
    else:
        conditions.append("e.status = 'published'")

    if filters.get("search"):
        conditions.append("(e.title ilike %s or e.description ilike %s)")
        term = f"%{filters['search']}%"
        params.extend([term, term])
    if filters.get("category"):
        conditions.append("c.name ilike %s")
        params.append(filters["category"])
    if filters.get("venue"):
        conditions.append("v.name ilike %s")
        params.append(filters["venue"])
    if filters.get("date"):
        conditions.append("e.event_date = %s")
        params.append(filters["date"])

    where = " where " + " and ".join(conditions) if conditions else ""
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""select count(*) from events e
                    join categories c on c.id = e.category_id
                    join venues v on v.id = e.venue_id{where}""",
                params,
            )
            total = cursor.fetchone()[0]
            cursor.execute(
                f"""select {EVENT_SELECT}
                    from events e
                    join categories c on c.id = e.category_id
                    join venues v on v.id = e.venue_id
                    join profiles p on p.id = e.organizer_id{where}
                    order by e.event_date asc, e.start_time asc
                    limit %s offset %s""",
                params + [limit, (page - 1) * limit],
            )
            columns = [description.name for description in cursor.description]
            return [serialize_event(row, columns) for row in cursor.fetchall()], total


def get_event(event_id):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            return _fetch_event(cursor, event_id)


def is_student_registered(event_id, student_id):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """select exists(select 1 from registrations
                   where event_id = %s and student_id = %s and status = 'registered')
                   or exists(select 1 from team_members tm join registrations r on r.team_id = tm.team_id
                   where r.event_id = %s and r.status = 'registered' and tm.student_id = %s)""",
                (event_id, student_id, event_id, student_id),
            )
            return cursor.fetchone()[0]


def create_event(payload, organizer_id):
    values = validate_event_payload(payload, requested_status=payload.get("status", "draft"))
    if values["status"] not in CREATE_STATUSES:
        raise ValueError("New events may only start as draft or pending")
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("select exists(select 1 from categories where id = %s)", (values["category_id"],))
            if not cursor.fetchone()[0]:
                raise LookupError("Category does not exist")
            cursor.execute("select exists(select 1 from venues where id = %s)", (values["venue_id"],))
            if not cursor.fetchone()[0]:
                raise LookupError("Venue does not exist")
            cursor.execute(
                """insert into events (title, description, category_id, organizer_id, venue_id,
                   event_date, start_time, end_time, capacity, registration_deadline, status, image_url,
                   participation_mode, min_team_size, max_team_size, eligibility, registration_instructions, facilities)
                   values (%(title)s, %(description)s, %(category_id)s, %(organizer_id)s, %(venue_id)s,
                   %(event_date)s, %(start_time)s, %(end_time)s, %(capacity)s, %(registration_deadline)s,
                   %(status)s, %(image_url)s, %(participation_mode)s, %(min_team_size)s, %(max_team_size)s,
                   %(eligibility)s, %(registration_instructions)s, %(facilities)s) returning id""",
                {**values, "organizer_id": organizer_id, "facilities": Jsonb(values["facilities"])},
            )
            event_id = cursor.fetchone()[0]
            return _fetch_event(cursor, event_id)


def update_event(event_id, payload):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            current = _fetch_event(cursor, event_id)
            if not current:
                return None
            source = dict(current)
            source["category_id"] = current["category"]["id"]
            source["venue_id"] = current["venue"]["id"]
            source["image_url"] = current["image_url"]
            source["participation_mode"] = current["participation_mode"]
            source["min_team_size"] = current["min_team_size"]
            source["max_team_size"] = current["max_team_size"]
            source["eligibility"] = current["eligibility"]
            source["registration_instructions"] = current["registration_instructions"]
            source["facilities"] = current["facilities"]
            source["status"] = current["status"]
            source["event_date"] = date.fromisoformat(current["event_date"])
            source["start_time"] = time.fromisoformat(current["start_time"])
            source["end_time"] = time.fromisoformat(current["end_time"])
            source["registration_deadline"] = datetime.fromisoformat(current["registration_deadline"].replace("Z", "+00:00"))
            requested_status = payload.get("status", current["status"]) if isinstance(payload, dict) else None
            values = validate_event_payload(payload, current=source, requested_status=requested_status)
            if values["status"] != current["status"] and values["status"] not in STATUS_TRANSITIONS[current["status"]]:
                raise ValueError(f"Cannot transition event from {current['status']} to {values['status']}")
            changed_fields = {
                field
                for field in ("title", "description", "category_id", "venue_id", "event_date", "start_time", "end_time", "capacity", "registration_deadline", "image_url", "participation_mode", "min_team_size", "max_team_size", "eligibility", "registration_instructions", "facilities")
                if values[field] != source.get(field)
            }
            active_ids = notification_service.active_registrant_ids(cursor, event_id) if current["status"] == "published" else []
            values["event_id"] = event_id
            values["facilities"] = Jsonb(values["facilities"])
            cursor.execute(
                """update events set title=%(title)s, description=%(description)s, category_id=%(category_id)s,
                   venue_id=%(venue_id)s, event_date=%(event_date)s, start_time=%(start_time)s,
                   end_time=%(end_time)s, capacity=%(capacity)s, registration_deadline=%(registration_deadline)s,
                   status=%(status)s, image_url=%(image_url)s, participation_mode=%(participation_mode)s,
                   min_team_size=%(min_team_size)s, max_team_size=%(max_team_size)s,
                   eligibility=%(eligibility)s, registration_instructions=%(registration_instructions)s,
                   facilities=%(facilities)s, updated_at=now()
                   where id=%(event_id)s""",
                values,
            )
            if active_ids and values["status"] == "published" and changed_fields:
                notification_service.create_notifications(
                    cursor,
                    active_ids,
                    "Event Updated",
                    f'The event "{values["title"]}" has been updated. Please review the latest event details.',
                    "event_update",
                )
            elif active_ids and values["status"] == "cancelled":
                notification_service.create_notifications(
                    cursor,
                    active_ids,
                    "Event Cancelled",
                    f'The event "{values["title"]}" has been cancelled.',
                    "cancellation",
                )
            return _fetch_event(cursor, event_id)


def change_status(event_id, new_status):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            current = _fetch_event(cursor, event_id)
            if not current:
                return None
            if new_status not in STATUS_TRANSITIONS[current["status"]]:
                raise ValueError(f"Cannot transition event from {current['status']} to {new_status}")
            active_ids = notification_service.active_registrant_ids(cursor, event_id) if new_status == "cancelled" else []
            cursor.execute("update events set status=%s, updated_at=now() where id=%s", (new_status, event_id))
            if active_ids:
                notification_service.create_notifications(
                    cursor,
                    active_ids,
                    "Event Cancelled",
                    f'The event "{current["title"]}" has been cancelled.',
                    "cancellation",
                )
            return _fetch_event(cursor, event_id)


def delete_event(event_id):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            current = _fetch_event(cursor, event_id)
            if not current:
                return None, False
            cursor.execute("select exists(select 1 from registrations where event_id=%s)", (event_id,))
            has_registrations = cursor.fetchone()[0]
            if has_registrations or current["status"] in {"published", "completed"}:
                active_ids = notification_service.active_registrant_ids(cursor, event_id)
                cursor.execute("update events set status='cancelled', updated_at=now() where id=%s", (event_id,))
                if active_ids:
                    notification_service.create_notifications(
                        cursor,
                        active_ids,
                        "Event Cancelled",
                        f'The event "{current["title"]}" has been cancelled.',
                        "cancellation",
                    )
                return _fetch_event(cursor, event_id), True
            cursor.execute("delete from events where id=%s", (event_id,))
            return current, False


def list_categories():
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("select id, name, description from categories order by name")
            return [{"id": str(row[0]), "name": row[1], "description": row[2]} for row in cursor.fetchall()]


def list_venues():
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("select id, name, location, capacity from venues order by name")
            return [{"id": str(row[0]), "name": row[1], "location": row[2], "capacity": row[3]} for row in cursor.fetchall()]


def list_faqs(event_id):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("select id, event_id, question, answer, position from event_faqs where event_id=%s order by position, created_at", (event_id,))
            return [{"id": str(row[0]), "event_id": str(row[1]), "question": row[2], "answer": row[3], "position": row[4]} for row in cursor.fetchall()]


def create_faq(event_id, payload):
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object")
    question, answer = payload.get("question"), payload.get("answer")
    if not isinstance(question, str) or not 3 <= len(question.strip()) <= 300:
        raise ValueError("question must be between 3 and 300 characters")
    if not isinstance(answer, str) or not 1 <= len(answer.strip()) <= 3000:
        raise ValueError("answer must be between 1 and 3000 characters")
    position = payload.get("position", 0)
    if isinstance(position, bool) or not isinstance(position, int) or position < 0:
        raise ValueError("position must be a non-negative integer")
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("insert into event_faqs(event_id, question, answer, position) values(%s,%s,%s,%s) returning id", (event_id, question.strip(), answer.strip(), position))
            faq_id = cursor.fetchone()[0]
            cursor.execute("select id, event_id, question, answer, position from event_faqs where id=%s", (faq_id,))
            row = cursor.fetchone()
            return {"id": str(row[0]), "event_id": str(row[1]), "question": row[2], "answer": row[3], "position": row[4]}


def update_faq(faq_id, payload):
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object")
    fields, params = [], []
    for name, limit in (("question", 300), ("answer", 3000)):
        if name in payload:
            value = payload[name]
            if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
                raise ValueError(f"{name} is invalid")
            fields.append(f"{name}=%s"); params.append(value.strip())
    if "position" in payload:
        if isinstance(payload["position"], bool) or not isinstance(payload["position"], int) or payload["position"] < 0:
            raise ValueError("position must be a non-negative integer")
        fields.append("position=%s"); params.append(payload["position"])
    if not fields:
        raise ValueError("At least one FAQ field is required")
    params.append(faq_id)
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(f"update event_faqs set {', '.join(fields)}, updated_at=now() where id=%s returning id, event_id, question, answer, position", params)
            row = cursor.fetchone()
            if not row:
                return None
            return {"id": str(row[0]), "event_id": str(row[1]), "question": row[2], "answer": row[3], "position": row[4]}


def delete_faq(faq_id):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("delete from event_faqs where id=%s returning event_id", (faq_id,))
            row = cursor.fetchone()
            return str(row[0]) if row else None


def faq_event_id(faq_id):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("select event_id from event_faqs where id=%s", (faq_id,))
            row = cursor.fetchone()
            return str(row[0]) if row else None
