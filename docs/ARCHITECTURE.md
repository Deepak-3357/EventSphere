# EventSphere Architecture

## 1. System overview

EventSphere is a campus event management portal for students, organizers, and administrators. The completed phases add Supabase Auth, profile synchronization, role protection, event workflows, attendance, dashboards, analytics, and OD letters.

```text
Browser
  | HTTP / Fetch API
  v
Frontend
  | Supabase Auth / REST API
  v
Flask Backend
  | PostgreSQL connection
  v
Supabase PostgreSQL
  ├── profiles
  ├── categories
  ├── venues
  ├── events
  ├── registrations
  └── notifications
  └── attendance
  └── od_letters
```

The Flask API now includes authentication, authorization, validation, and an Event Service between the browser and the `events` table.

Student registration follows `event details → register → validation/capacity/duplicate transaction → registrations`. Registration reads remain ownership-scoped by RLS, and registration writes remain in the Flask service layer. A student pass is generated from an active registration and signed by the backend; organizers/admins submit the scanned payload to the attendance service.

Event and registration actions can call the Notification Service in the same database transaction:

```text
Registration/Event Action
        ↓
Notification Service
        ↓
notifications
        ↓
Notification API
        ↓
Notification Center
```

## 2. Client-server architecture

The browser owns presentation and user interaction. It communicates with the Flask backend over HTTP using the Fetch API. The backend remains the application and validation layer rather than allowing the browser to access PostgreSQL directly.

## 3. Frontend

The `frontend/` directory contains the Bootstrap landing page, Auth pages, role dashboards, event/registration/attendance/OD workflows, custom CSS, and Fetch API interactions.

## 4. Flask backend

The `backend/` directory uses an application factory in `backend/app/__init__.py`. Routes are grouped into blueprints and business logic is kept in service modules. Configuration is read from environment variables in `backend/config.py`. Auth routes verify Supabase bearer tokens before loading a profile and role.

## 5. Supabase PostgreSQL

Supabase PostgreSQL is the persistence layer. Migrations create the eight application tables, constraints, indexes, seed data, and RLS policies. Database credentials remain in the local ignored `.env` file.

## 6. Authentication

Supabase Auth handles email/password identity and sessions. The browser uses the public publishable key for sign-up/sign-in, while Flask verifies bearer tokens and reads the role from `profiles`. A database trigger creates a profile for each new Auth user.

## 7. REST API layer

The REST layer includes event, registration, notification, event-pass, check-in, and attendance-report endpoints. See [ATTENDANCE_API.md](ATTENDANCE_API.md) for the Phase 7 contract.

Phase 8 adds role-scoped dashboard aggregates and an OD letter service. Dashboard SQL applies the authenticated student or organizer ID directly; admin aggregates are platform-wide. OD PDFs and signed verification tokens are generated server-side. The public event catalog is also available as XML at `/api/events/export.xml` to demonstrate both JSON REST and XML representations.

## 8. User roles

- **Student:** discover events and manage registrations.
- **Organizer:** create and manage event information.
- **Admin:** manage users, events, publication approval, and reports.

## 9. Deployment boundary

The recommended deployment is a static frontend host plus a production WSGI Flask host connected to Supabase PostgreSQL/Auth. The browser receives only the Supabase publishable key and API base configuration; database and signing secrets remain server-side.
