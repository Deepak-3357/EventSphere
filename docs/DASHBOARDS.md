# Role-based dashboards

Phase 8 provides three dashboard APIs and Bootstrap/vanilla JavaScript pages:

- `GET /api/dashboard/student` — authenticated student only; aggregates only that student's registrations, attendance, notifications, and upcoming registered events.
- `GET /api/dashboard/organizer` — authenticated organizer only; every aggregate and event row is filtered by `events.organizer_id = auth user` in SQL.
- `GET /api/dashboard/admin` — authenticated admin only; platform-wide user, event, registration, attendance, category, and status aggregates.

The pages live under `frontend/dashboard/student/`, `frontend/dashboard/organizer/`, and `frontend/dashboard/admin/`. They share the existing Supabase session client, Flask bearer-token middleware, responsive Bootstrap layout, notification unread-count endpoint, and existing event/attendance pages. Chart.js is used only for compact organizer and admin summaries.

Frontend role checks are only for presentation. The backend decorators and SQL ownership filters remain authoritative. Loading, empty, and error states are rendered explicitly.
