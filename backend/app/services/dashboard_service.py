"""Database-scoped dashboard aggregates for each authenticated role."""

from app.db import get_connection


def _value(value):
    return value.isoformat() if hasattr(value, "isoformat") else value


def _rows(cursor):
    columns = [item.name for item in cursor.description]
    return [{column: _value(value) for column, value in zip(columns, row)} for row in cursor.fetchall()]


def student_dashboard(student_id):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """select count(*) filter (where r.status = 'registered') as registrations,
                          count(*) filter (where r.status = 'registered' and e.event_date >= current_date and e.status = 'published') as upcoming_events,
                          count(*) filter (where a.status = 'present') as checked_in
                   from registrations r join events e on e.id = r.event_id
                   left join attendance a on a.registration_id = r.id
                   where r.student_id = %s""", (student_id,))
            stats = dict(zip([item.name for item in cursor.description], cursor.fetchone()))
            cursor.execute("select count(*) from notifications where user_id = %s and is_read = false", (student_id,))
            stats["unread_notifications"] = cursor.fetchone()[0]
            cursor.execute(
                """select r.id as registration_id, e.id as event_id, e.title, e.event_date,
                          e.start_time, e.end_time, v.name as venue_name,
                          r.status as registration_status, coalesce(a.status, 'not_checked_in') as attendance_status
                   from registrations r join events e on e.id = r.event_id
                   join venues v on v.id = e.venue_id left join attendance a on a.registration_id = r.id
                   where r.student_id = %s and r.status = 'registered' and e.status = 'published' and e.event_date >= current_date
                   order by e.event_date, e.start_time limit 5""", (student_id,))
            upcoming = _rows(cursor)
            cursor.execute(
                """select r.id as registration_id, e.title, e.event_date, r.status,
                          coalesce(a.status, 'not_checked_in') as attendance_status
                   from registrations r join events e on e.id = r.event_id
                   left join attendance a on a.registration_id = r.id
                   where r.student_id = %s order by r.registered_at desc limit 5""", (student_id,))
            registrations = _rows(cursor)
            cursor.execute("""select title, message, type, is_read, created_at from notifications
                             where user_id = %s order by created_at desc limit 5""", (student_id,))
            notifications = _rows(cursor)
            return {"stats": stats, "upcoming_events": upcoming, "recent_registrations": registrations,
                    "recent_notifications": notifications}


def organizer_dashboard(organizer_id):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """select count(e.id) as total_events,
                          coalesce(sum((select count(*) from registrations r where r.event_id = e.id and r.status = 'registered')), 0)::int as total_registrations,
                          coalesce(sum((select count(*) from attendance a where a.event_id = e.id and a.status = 'present')), 0)::int as total_checked_in,
                          count(e.id) filter (where e.event_date >= current_date and e.status = 'published') as upcoming_events
                   from events e
                   where e.organizer_id = %s""", (organizer_id,))
            stats = dict(zip([item.name for item in cursor.description], cursor.fetchone()))
            cursor.execute(
                """select e.id, e.title, e.event_date, e.status, e.capacity,
                          (select count(*) from registrations r where r.event_id = e.id and r.status = 'registered')::int as registrations,
                          (select count(*) from attendance a where a.event_id = e.id and a.status = 'present')::int as checked_in
                   from events e
                   where e.organizer_id = %s order by e.event_date desc limit 20""", (organizer_id,))
            events = _rows(cursor)
            cursor.execute("""select e.status, count(*)::int as count from events e where e.organizer_id = %s
                             group by e.status order by e.status""", (organizer_id,))
            statuses = _rows(cursor)
            return {"stats": stats, "events": events, "analytics": {"status_distribution": statuses}}


def admin_dashboard():
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""select count(*) as total_users,
                                      count(*) filter (where role = 'student') as total_students,
                                      count(*) filter (where role = 'organizer') as total_organizers,
                                      count(*) filter (where role = 'admin') as total_admins from profiles""")
            stats = dict(zip([item.name for item in cursor.description], cursor.fetchone()))
            cursor.execute("""select count(*) as total_events,
                                      count(*) filter (where event_date >= current_date and status = 'published') as upcoming_events from events""")
            stats.update(dict(zip([item.name for item in cursor.description], cursor.fetchone())))
            cursor.execute("select count(*) filter (where status = 'registered') from registrations")
            stats["total_registrations"] = cursor.fetchone()[0]
            cursor.execute("select count(*) filter (where status = 'present') from attendance")
            stats["total_attendance"] = cursor.fetchone()[0]
            cursor.execute("""select status, count(*)::int as count from events group by status order by status""")
            statuses = _rows(cursor)
            cursor.execute("""select c.name, count(e.id)::int as count from categories c left join events e on e.category_id = c.id
                             group by c.name order by count desc, c.name limit 10""")
            categories = _rows(cursor)
            return {"stats": stats, "analytics": {"status_distribution": statuses, "events_by_category": categories}}
