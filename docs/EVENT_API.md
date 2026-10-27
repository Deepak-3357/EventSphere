# Event Management API

## Overview

Phase 4 adds REST event management through Flask. The API uses the existing Supabase PostgreSQL `events`, `categories`, and `profiles` tables. Registration and notification workflows are intentionally deferred.

Base URL: `http://127.0.0.1:5000/api`

Protected requests use:

```http
Authorization: Bearer <SUPABASE_ACCESS_TOKEN>
```

## Endpoints

| Method | Endpoint | Access |
|---|---|---|
| GET | `/events` | Public published events; organizer/admin management views |
| GET | `/events/<id>` | Public published events; owner/admin private details |
| POST | `/events` | Organizer or admin |
| PUT | `/events/<id>` | Owner organizer or admin |
| DELETE | `/events/<id>` | Owner organizer or admin |
| PATCH | `/events/<id>/publish` | Owner organizer or admin |
| PATCH | `/events/<id>/cancel` | Owner organizer or admin |
| GET | `/categories` | Public |

## Create/update request

```json
{
  "title": "Campus Hack Day",
  "description": "A collaborative day of prototyping.",
  "category_id": "10000000-0000-0000-0000-000000000001",
  "event_date": "2099-11-14",
  "start_time": "09:00",
  "end_time": "17:00",
  "capacity": 80,
  "registration_deadline": "2099-11-13T18:00:00+05:30",
  "status": "draft",
  "image_url": "https://example.com/event.png"
}
```

`organizer_id`, `user_id`, and `role` in the request body are ignored. The organizer is derived from the verified bearer token. New events may begin as `draft` or `pending`.

## List filters and pagination

`GET /events` supports:

- `page` — one-based page number, default `1`
- `limit` — default `10`, maximum `100`
- `search` — title/description search
- `category` — category name filter
- `date` — `YYYY-MM-DD`
- `status` — private statuses require organizer/admin authorization

Unauthenticated and student requests only see `published` events. Organizers see published events plus their own events. Admins can use status filters across management data.

## Response format

Success:

```json
{
  "success": true,
  "data": {}
}
```

Collections include:

```json
{
  "success": true,
  "data": [],
  "pagination": {"page": 1, "limit": 10, "total": 3}
}
```

Errors use:

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "end_time must be after start_time",
    "details": {}
  }
}
```

HTTP statuses include `200`, `201`, `401`, `403`, `404`, `422`, and `500`.

## Validation

The backend validates required fields, UUID references, title/description length, ISO dates, time ordering, positive capacity, deadline before event start, allowed statuses, and HTTP(S) image URLs. Category references must exist.

## Lifecycle

```text
draft ──> pending ──> published ──> completed
  │          │            │
  └──────────┴────────────┴──> cancelled
```

For the current academic workflow, an eligible draft may also be published directly. Completed and cancelled events are terminal. Deleting a published/completed event, or any event with registrations, performs soft cancellation to preserve historical data; draft/pending events without registrations can be physically deleted.

## Security

Authentication and role checks are server-side. Ownership is compared with the verified Auth user ID. SQL uses parameterized psycopg queries. Raw database exceptions and credentials are never returned to clients. Service-role credentials are not sent to the browser.

## Example requests

```powershell
Invoke-RestMethod http://127.0.0.1:5000/api/events
Invoke-RestMethod 'http://127.0.0.1:5000/api/events?search=hack&limit=10'
```

For protected requests, add an `Authorization` header containing a short-lived Supabase access token. Never save real tokens in this repository.
## XML catalog

`GET /api/events/export.xml` returns up to 100 published events as `application/xml`. It is intentionally public like the published JSON catalog and uses the same server-side event query; XML element serialization escapes titles, descriptions, and categories safely.
