# EventSphere database design

## ER-style overview

```text
profiles
   │
   ├──< events
   ├──< registrations
   └──< notifications

categories ──< events
venues ──────< events
events ──────< registrations
registrations ── attendance (one check-in per registration)
events ──────< attendance
profiles ────< attendance (student and scanner)
registrations ──< od_letters
profiles ───────< od_letters
```

## Design decisions

- All application tables use UUID primary keys with PostgreSQL-generated defaults.
- `profiles` is an application profile table intended to align with Supabase Auth later; it deliberately has no password column.
- Role, event status, registration status, and notification type use check constraints to keep values predictable.
- Required names and text fields reject blank strings, not only `NULL`.
- Event time ordering is enforced with `end_time > start_time`; capacity values must be positive.
- Foreign keys use `ON DELETE RESTRICT` so an organizer, venue, event, or profile cannot be removed while historical records depend on it.
- The unique `(event_id, student_id)` constraint prevents duplicate registrations at the database level.
- Indexes support event discovery, organizer/category/venue filtering, registration lookup, user notification lookup, and attendance reporting.
- `attendance.registration_id` is unique, and all attendance foreign keys use `ON DELETE RESTRICT` to preserve audit history.
- `od_letters.registration_id` and `od_letters.letter_number` are unique. OD records retain history while PDF download checks that the source registration is still active.

## Supabase and security

The migrations contain no credentials. The enhancement migrations add validated event participation settings (`individual`, `team`, or `both`), optional team-size limits, eligibility/instructions, JSON facility details, the organizer-owned `event_faqs` table, and normalized `teams`/`team_members` records linked to a registration. Existing registrations default to individual participation. Team registration locks the event row, counts one team registration against capacity, validates the configured size, stores the verified leader plus submitted member details, and keeps the registration row as the attendance/OD anchor. RLS permits public reads only for published-event FAQs; Flask remains the write path and checks event ownership/admin access. RLS is enabled for profiles, events, registrations, notifications, attendance, OD letters, teams, and team members. Attendance reads are limited to the student, owning organizer, or admin; OD-letter direct reads are limited to the owning student; no client attendance/OD write policies exist. The Flask backend keeps signing secrets server-side.
