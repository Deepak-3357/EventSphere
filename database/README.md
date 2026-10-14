# EventSphere database

EventSphere uses Supabase PostgreSQL behind the Flask REST API. Phase 2 creates six relational tables and development seed data. Authentication remains a Phase 3 concern; `profiles` stores application data and never stores passwords.

## Tables and relationships

```text
profiles
   │
   ├──< events          (events.organizer_id)
   ├──< registrations   (registrations.student_id)
   └──< notifications   (notifications.user_id)

categories ──< events   (events.category_id)
venues ──────< events   (events.venue_id)
events ──────< registrations (registrations.event_id)
```

The full reproducible schema is in `supabase/migrations/20261008120000_initial_event_sphere_schema.sql`.

## Schema summary

- `profiles`: UUID primary key, unique email, role check (`student`, `organizer`, `admin`), optional department/year, timestamps.
- `categories`: UUID primary key, unique non-empty name, description, creation timestamp.
- `venues`: UUID primary key, unique non-empty name, location, positive capacity, creation timestamp.
- `events`: UUID primary key, title/description, category/organizer/venue foreign keys, date/time, positive capacity, deadline, status check, timestamps.
- `registrations`: UUID primary key, event/student foreign keys, status check, timestamp, unique `(event_id, student_id)`.
- `notifications`: UUID primary key, user foreign key, non-empty title/message, type check, read flag, timestamp.

Foreign keys use `ON DELETE RESTRICT` to protect historical event, registration, and notification records. Registration duplication is prevented by a unique constraint. Indexes cover foreign keys, event date/status, and notification lookup by user/time.

## Seed data

`database/seed.sql` contains fake deterministic profiles, categories, venues, events, registrations, and notifications. It contains no passwords or real personal data and can be safely re-run because inserts are conflict-aware.

## Initialization

```powershell
py backend\scripts\apply_migrations.py
```

The script reads `.env`, connects with psycopg using separate connection parameters (so special characters in the password are handled safely), and executes the migration followed by the seed file. Required variables are documented in `.env.example`.

## Deployment order

Render deploys `backend/` and Supabase holds the schema, so the two move independently. **Apply migrations before deploying backend code that depends on them.** A backend that selects a column the database does not have yet fails every request that touches that column, and the API reports it to users as a generic `The event request could not be completed.` — this is what took out both event lists when `20261012100000_manual_event_lifecycle.sql` was committed but not applied.

`GET /api/health/schema` reports whether the connected database matches the deployed code. It returns `503` and names the missing tables/columns while a migration is still pending, so a half-applied deployment is visible at deploy time instead of silent. `tests/test_schema_contract.py` enforces the same contract offline.

The migration set as a whole is **not** re-runnable against an existing database: several files add constraints and triggers without a preceding `drop`, so re-running everything fails partway. Apply only the pending file — every statement in it is guarded — for example by pasting `supabase/migrations/20261012100000_manual_event_lifecycle.sql` into the Supabase SQL editor, or:

```powershell
psql -h <host> -U postgres -d postgres -f supabase\migrations\20261012100000_manual_event_lifecycle.sql
```

`py backend\scripts\apply_migrations.py` runs the whole set plus the seed and is intended for a fresh local database, not for production catch-up.
