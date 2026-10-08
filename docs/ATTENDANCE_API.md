# Attendance and event passes

Phase 7 adds server-signed student event passes and organizer/admin attendance scanning.

## Student pass

`GET /api/registrations/<registration_id>/pass`

Requires a Supabase bearer token for the student who owns an active registration. The response includes safe event and student display data, the current attendance state, and an opaque JSON QR payload. The payload contains only an EventSphere type, registration ID, and HMAC signature; it does not contain credentials or editable attendance fields. Cancelled or completed registrations cannot obtain a pass.

## Check-in

`POST /api/attendance/check-in`

Requires an organizer or admin bearer token and JSON such as:

```json
{"qr_payload":"{...signed pass payload...}"}
```

The API verifies the signature, active registration, event ownership, and configurable time window before inserting one `present` row. Replays return `409 ALREADY_CHECKED_IN`; malformed or tampered payloads return `400`; an organizer scanning another organizer's event returns `403`.

The window is controlled by `ATTENDANCE_EARLY_MINUTES` and `ATTENDANCE_LATE_MINUTES` (defaults 30 and 120). Event date/time values are evaluated in the application/database local time used by the deployment.

## Attendance report

`GET /api/events/<event_id>/attendance`

Organizers can read their own event report and admins can read every event report. Students are denied. The response contains event details, `registered`, `checked_in`, `absent`, `attendance_percentage`, and attendee rows with registration ID, safe profile fields, status, and check-in time.

## Security and database

Attendance has a unique constraint on `registration_id`, restrictive foreign keys, indexes for event/student/registration/scanner/time, and RLS select policies for the student, owning organizer, or admin. There are no client insert/update/delete policies; writes are performed by the Flask service after validation. Keep `ATTENDANCE_QR_SECRET` server-side and rotate it if pass payloads need to be invalidated.

The browser scanner uses `html5-qrcode` from a CDN and requests camera access locally. Camera access normally requires localhost or HTTPS; image upload is not supported.
