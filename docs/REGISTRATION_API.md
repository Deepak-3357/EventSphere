# Student registration API

## Architecture

```text
Student → Event Details → Register
                    ↓
              Flask REST API
                ├─ Auth/RBAC
                ├─ Eligibility validation
                ├─ Event row lock
                ├─ Capacity check
                ├─ Duplicate check
                └─ Transaction
                    ↓
              Supabase PostgreSQL
                 registrations
```

## Endpoints

| Method | Endpoint | Access |
|---|---|---|
| POST | `/api/events/<event_id>/register` | Authenticated student |
| DELETE | `/api/events/<event_id>/register` | Authenticated student who owns the registration |
| GET | `/api/my-registrations` | Authenticated student |
| GET | `/api/registrations/<registration_id>` | Registration owner, event organizer, or admin |
| GET | `/api/events/<event_id>/registrations` | Event organizer or admin |
| GET | `/api/registrations` | Admin |

Protected requests use `Authorization: Bearer <SUPABASE_ACCESS_TOKEN>`. Student identity always comes from the verified token; request-body and query-string student IDs are not used for student actions.

## Registration rules

Registration requires a published event, a future registration deadline, available capacity, and a student role. Draft, pending, cancelled, and completed events reject registration. Active duplicate registrations return `409 ALREADY_REGISTERED`.

The existing unique `(event_id, student_id)` constraint remains in place. A cancelled row is reactivated instead of inserting a second row, preserving registration history while preventing duplicate active records.

## Capacity and concurrency

Registration opens a database transaction and locks the event row with `SELECT ... FOR UPDATE`. It then checks the deadline, locks the student’s existing registration if present, counts only rows with `status = 'registered'`, and inserts or reactivates the registration before commit. Concurrent attempts for the final seat serialize on the event row, so capacity cannot be exceeded by a check-then-insert race.

Cancelled registrations do not count toward capacity. Event details expose `registered_count` and `available_seats`; student-authenticated details also expose `is_registered`.

## Cancellation and re-registration

`DELETE /api/events/<event_id>/register` changes the student’s row to `cancelled`; it does not delete history. A later registration reactivates that same row when the event remains eligible.

## Registration views

Students receive only their own registrations from `/api/my-registrations`. `status=registered`, `status=cancelled`, and `upcoming=true` are supported. Organizers can view participants only for their own events. Admins can filter `/api/registrations` by `event_id`, `student_id`, and `status`.

Responses use the standard format:

```json
{
  "success": true,
  "data": {}
}
```

Business-rule failures use `409`, validation failures use `422`, missing/unauthorized resources use `401`/`403`/`404`, and database failures return a generic `500` message without raw SQL details.

## RLS

RLS remains enabled. Registration reads are allowed for the student owner, the organizer of the related event, or an admin. Registration writes remain server-side through Flask so the transaction, capacity lock, and ownership checks are applied consistently. Service-role credentials are never sent to the frontend.

## Frontend test pages

- Browse: `http://127.0.0.1:5500/events/`
- Event details: select an event, then use Register/Cancel
- My registrations: `http://127.0.0.1:5500/student/registrations/`

These are minimal workflow pages, not the final dashboard design.
## Individual and team registration

`POST /api/events/<event_id>/register` accepts an optional JSON body. Omit it, or send `{"participation_type":"individual"}`, for the existing individual flow. For a team event send:

```json
{
  "participation_type": "team",
  "team": {
    "name": "Blue Orbit",
    "members": [
      {"full_name": "Member Two", "email": "member.two@example.test", "department": "Computer Science", "year": 2}
    ]
  }
}
```

The authenticated student is always the team leader and is added from the verified profile; client-supplied user IDs are ignored. The backend enforces the event mode, configured team-size bounds, unique member emails, active duplicate registrations, deadline, and capacity while holding the event row lock. Registration responses and registration-list records include `participation_type` and a team member list. Cancellation preserves the team/member history and marks the registration cancelled; re-registration reactivates the same registration after validating the submitted team again.
