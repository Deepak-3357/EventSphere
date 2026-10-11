# React dashboard endpoint map

The Phase 4 preview dashboard uses the existing role-scoped Flask endpoints. The browser sends the existing Supabase access token as a bearer token; role and ownership remain backend-authoritative.

| Dashboard | Endpoint | Data rendered |
| --- | --- | --- |
| Student | `GET /api/dashboard/student` | Registration counts, upcoming registered events, recent registrations, recent notifications |
| Organizer | `GET /api/dashboard/organizer` | Managed event counts, event rows, registration/check-in counts, status distribution |
| Admin | `GET /api/dashboard/admin` | User/event/registration/attendance totals, event status distribution, category analytics |

Legacy routes remain the target for pages without a React replacement, including event management, detailed event pages, OD letters, notifications, and the existing attendance/pass workflows.
