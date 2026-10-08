"""Database-backed in-app notification operations."""

from uuid import UUID

from app.db import get_connection


NOTIFICATION_TYPES = {"registration", "event_update", "cancellation", "reminder", "system"}


def _serialize(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    return value


def create_notification(cursor, user_id, title, message, notification_type):
    """Insert one notification using the caller's active transaction."""

    if notification_type not in NOTIFICATION_TYPES:
        raise ValueError("Invalid notification type")
    cursor.execute(
        """insert into notifications (user_id, title, message, type)
           values (%s, %s, %s, %s)
           returning id, user_id, title, message, type, is_read, created_at""",
        (user_id, title, message, notification_type),
    )
    return cursor.fetchone()


def create_notifications(cursor, user_ids, title, message, notification_type):
    """Bulk insert notifications for unique recipients in one transaction."""

    unique_user_ids = list(dict.fromkeys(user_ids))
    if not unique_user_ids:
        return 0
    if notification_type not in NOTIFICATION_TYPES:
        raise ValueError("Invalid notification type")
    cursor.executemany(
        """insert into notifications (user_id, title, message, type)
           values (%s, %s, %s, %s)""",
        [(user_id, title, message, notification_type) for user_id in unique_user_ids],
    )
    return len(unique_user_ids)


def active_registrant_ids(cursor, event_id):
    cursor.execute(
        "select student_id from registrations where event_id = %s and status = 'registered'",
        (event_id,),
    )
    return [row[0] for row in cursor.fetchall()]


def list_user_notifications(user_id, page=1, limit=10, unread=None, notification_type=None):
    conditions = ["user_id = %s"]
    params = [user_id]
    if unread is not None:
        conditions.append("is_read = %s")
        params.append(unread)
    if notification_type:
        if notification_type not in NOTIFICATION_TYPES:
            raise ValueError("Invalid notification type")
        conditions.append("type = %s")
        params.append(notification_type)
    where = " and ".join(conditions)
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(f"select count(*) from notifications where {where}", params)
            total = cursor.fetchone()[0]
            cursor.execute(
                f"""select id, user_id, title, message, type, is_read, created_at
                    from notifications where {where}
                    order by created_at desc limit %s offset %s""",
                params + [limit, (page - 1) * limit],
            )
            columns = [description.name for description in cursor.description]
            items = [
                {column: _serialize(value) for column, value in zip(columns, row)}
                for row in cursor.fetchall()
            ]
            return items, total


def unread_count(user_id):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "select count(*) from notifications where user_id = %s and is_read = false",
                (user_id,),
            )
            return cursor.fetchone()[0]


def mark_notification_read(notification_id, user_id):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """update notifications set is_read = true
                   where id = %s and user_id = %s
                   returning id, is_read""",
                (notification_id, user_id),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return {"id": str(row[0]), "is_read": row[1]}


def mark_all_read(user_id):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "update notifications set is_read = true where user_id = %s and is_read = false",
                (user_id,),
            )
            return cursor.rowcount
