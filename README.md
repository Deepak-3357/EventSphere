# EventSphere

EventSphere is a campus event management portal for discovering, organizing, and managing university events. Phases 1–9 cover authentication, event management, registrations, notifications, signed event passes, attendance, role-based dashboards, analytics, OD letters, and final security/deployment readiness.

## Technology stack

- Frontend: HTML5, CSS3, Bootstrap 5, JavaScript, Fetch API
- Backend: Python and Flask REST API
- Database/cloud: Supabase PostgreSQL
- Database driver: psycopg
- Authentication: Supabase Authentication with bearer-token verification
- PDF: ReportLab
- QR: qrcode with server-signed verification payloads

## Architecture

```text
Browser (HTML/CSS/JavaScript)
          |
       Fetch API
          v
     Flask REST API
          |
          v
  Supabase PostgreSQL
```

The Flask backend is the main application/API layer. The frontend does not connect directly to Supabase or expose server credentials.

## User roles

- **Student:** browse events, register, cancel registrations, view notifications, and show event passes.
- **Organizer:** create and manage events, participants, and owned-event attendance.
- **Admin:** manage users/events and view or record attendance for all events.


## Development setup

1. Copy `.env.example` to `.env` and fill in local values when Supabase integration is introduced. Never commit `.env`.
2. Create and activate a virtual environment:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. Install backend dependencies:

   ```powershell
   py -m pip install -r backend\requirements.txt
   ```

## Start the Flask backend

From the repository root:

```powershell
py backend\run.py
```

The API listens at `http://127.0.0.1:5000`.

## Start the frontend locally

In a second terminal from the repository root:

```powershell
py -m http.server 5500 --directory frontend
```

Open `http://127.0.0.1:5500`. The “Check API status” button uses Fetch API to call the local Flask health endpoint.

## Health check

`GET http://127.0.0.1:5000/api/health` returns:

```json
{
  "status": "ok",
  "service": "EventSphere API"
}
```

## Database and Supabase

The expected Supabase project reference is documented in `database/README.md`. Phase 2 adds a reproducible migration under `supabase/migrations/`, seed data under `database/seed.sql`, and a psycopg connection layer. Run `py backend\scripts\apply_migrations.py` after configuring the local `.env` file.

Apply pending migrations **before** deploying backend code that depends on them: Render ships the Flask code while Supabase holds the schema, and a backend that selects a column the database does not have yet turns every affected route into a generic 500. `GET /api/health/schema` reports `503` with the missing objects while a migration is pending. See `database/README.md` for the production catch-up procedure.

The final schema includes `profiles`, `categories`, `venues`, `events`, `registrations`, `notifications`, `attendance`, and `od_letters`. RLS policies restrict direct authenticated reads by ownership; Flask remains the validated write path.

## Authentication

Phase 3 uses Supabase Auth for email/password registration, login, logout, and sessions. Public registration always creates a student profile. Organizer/admin roles are controlled outside the public form. The Flask API verifies Supabase bearer tokens and loads roles from `profiles`; see [docs/AUTHENTICATION.md](docs/AUTHENTICATION.md).

Authentication pages are available at:

- `http://127.0.0.1:5500/login/`
- `http://127.0.0.1:5500/register/`

Run database migrations and tests with:

```powershell
py backend\scripts\apply_migrations.py
py -m unittest discover -s tests -v
```

## Event API

Phase 4 provides event CRUD, organizer ownership checks, admin management, published-event browsing, search/filter/pagination, category/venue lookups, validation, lifecycle actions, and a public XML catalog at `/api/events/export.xml`. See [docs/EVENT_API.md](docs/EVENT_API.md).

## Student registrations

Phase 5 adds authenticated student registration and cancellation, capacity-safe transactions, re-registration of cancelled rows, student registration history, organizer participant views, and admin registration filters. See [docs/REGISTRATION_API.md](docs/REGISTRATION_API.md).

Minimal workflow pages:

- `http://127.0.0.1:5500/events/`
- `http://127.0.0.1:5500/student/registrations/`

## Notifications

Phase 6 adds transactional in-app notifications for registrations, cancellations, and meaningful updates to published events. Authenticated users can view and manage their own notifications at `http://127.0.0.1:5500/notifications/`. See [docs/NOTIFICATIONS_API.md](docs/NOTIFICATIONS_API.md). Email delivery and reminders are deferred.

## Attendance and event passes

Phase 7 adds the RLS-protected `attendance` table, HMAC-signed student QR passes, role- and ownership-checked check-in, configurable attendance windows, and attendance reports. See [docs/ATTENDANCE_API.md](docs/ATTENDANCE_API.md).

Student pass page: `http://127.0.0.1:5500/student/event-pass/?registration_id=<id>`

Organizer scanner: `http://127.0.0.1:5500/organizer/attendance/`

Admin scanner: `http://127.0.0.1:5500/admin/attendance/`

## Dashboards and OD letters

Phase 8 adds SQL-scoped student, organizer, and admin dashboards, responsive navigation, organizer/admin charts, and student OD letter generation. See [docs/DASHBOARDS.md](docs/DASHBOARDS.md) and [docs/OD_LETTERS.md](docs/OD_LETTERS.md).

Student dashboard: `http://127.0.0.1:5500/dashboard/student/`

Organizer dashboard: `http://127.0.0.1:5500/dashboard/organizer/`

Admin dashboard: `http://127.0.0.1:5500/dashboard/admin/`

## Security and deployment

Secrets are environment variables and `.env` is ignored. Configure `SUPABASE_URL`, `SUPABASE_ANON_KEY`, database connection values, attendance/OD signing secrets, and `FRONTEND_ORIGIN`; keep Flask debug disabled in production. The recommended deployment is a static frontend host plus a production WSGI Flask host connected to Supabase PostgreSQL/Auth. Set `window.EVENTSPHERE_API_BASE_URL` before frontend scripts when the API is not on the local development address.

The project demonstrates HTML5, CSS3, JavaScript, HTTP request/response, JSON REST APIs, XML export, database CRUD, authentication, authorization, validation, security controls, automated testing, and documentation. SOAP is not implemented because no explicit SOAP contract was provided; XML is demonstrated by the published event catalog export.

## Final validation and demo

Run `py -m pytest -q`, `py -m unittest discover -s tests -v`, `py -m compileall -q backend tests`, and JavaScript syntax checks. See [docs/TESTING.md](docs/TESTING.md) and [docs/DEMO_FLOW.md](docs/DEMO_FLOW.md). Live camera permission and browser-responsive inspection remain manual checks.
