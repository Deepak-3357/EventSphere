# EventSphere notification system

## Architecture

```text
Event / registration action
          ↓
Notification service
          ↓
notifications table
          ↓
Notification API
          ↓
Notification center
```

Notifications are in-app database records. No email provider, queue, worker, or external notification service is introduced in Phase 6.

## Notification types

- `registration` — registration confirmed
- `cancellation` — registration or event cancellation
- `event_update` — meaningful update to a published event
- `reminder` — reserved for a future scheduled mechanism
- `system` — general system notices

## APIs

| Method | Endpoint | Access |
|---|---|---|
| GET | `/api/notifications` | Authenticated user’s notifications |
| GET | `/api/notifications/unread-count` | Authenticated user |
| PATCH | `/api/notifications/<id>/read` | Notification owner |
| PATCH | `/api/notifications/read-all` | Authenticated user |

`GET /api/notifications` supports `page`, `limit`, `unread=true|false`, and `type`. Results are newest first. User identity always comes from the verified Auth token; `user_id` query/body values are ignored.

## Automatic generation

- Successful registration or re-registration creates `Registration Confirmed` for the student.
- Successful registration cancellation creates `Registration Cancelled` for the student.
- Meaningful updates to a published event create `Event Updated` for active registrants only.
- Event cancellation creates `Event Cancelled` for active registrants only.
- Cancelled registrations are excluded.
- Publishing does not broadcast notifications because EventSphere has no subscription model.
- Failed actions create no notification.
- Repeating cancellation on an already cancelled event is rejected and creates no duplicate notification.

## Transaction strategy

Registration/cancellation and their notification inserts run in the same psycopg transaction. Event updates/cancellations and bulk notification inserts also run in the same transaction. If notification insertion fails, the parent action rolls back rather than leaving an inconsistent success state.

## Bulk notifications and duplicates

The service collects unique active student IDs and uses one `executemany` bulk insert within the parent transaction. Notifications are generated only for meaningful published-event changes and valid state transitions; no separate deduplication table is needed for this phase.

## Authorization and RLS

All notification APIs require authentication. Students, organizers, and admins can access only their own notifications. The notification RLS policy permits users to select and update rows where `user_id = auth.uid()`, while inserts remain controlled by the Flask service layer.

## Example responses

```json
{
  "success": true,
  "data": {
    "unread_count": 3
  }
}
```

```json
{
  "success": false,
  "error": {
    "code": "NOT_FOUND",
    "message": "Notification not found",
    "details": {}
  }
}
```

## Frontend

The minimal notification center is at `http://127.0.0.1:5500/notifications/`. It supports newest-first listing, unread styling, mark-read, mark-all-read, loading, empty, and error states. The public navigation displays a live unread badge when a Supabase session exists.

Reminder scheduling is intentionally documented for a later phase; no Celery, Redis, cron, or background worker was added.
