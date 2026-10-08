# Testing and final audit

## Automated strategy

The suite uses Flask's test client with mocked Supabase token verification and a configured PostgreSQL integration database. Tests exercise authentication, role authorization, ownership boundaries, event lifecycle, registrations, notifications, attendance/QR validation, dashboard scopes, OD authorization, PDF generation, and public OD verification.

Run:

```powershell
py -m pytest -q
py -m unittest discover -s tests -v
py -m compileall -q backend tests
```

The final audit suite passed 42 tests with pytest. The tests also parse a generated one-page PDF with pypdf and verify signed/tampered OD and attendance tokens.

## Security matrix

| Case | Expected | Result |
|---|---:|---|
| Unauthenticated student dashboard | 401 | Passed |
| Student → organizer dashboard | 403 | Passed |
| Organizer → admin dashboard | 403 | Passed by role middleware coverage |
| Organizer A → Organizer B dashboard data | No B data | Passed |
| Student A → Student B registration/pass/OD | 404 | Passed |
| Student → attendance check-in/report | 403 | Passed |
| Tampered attendance QR | 400 | Passed |
| Duplicate attendance scan | 409 | Passed |
| Cancelled registration → OD download | 409 | Passed |
| Invalid OD verification token | 404 | Passed |

## Manual-only checks

Live Supabase email login, browser camera permission/QR scanning, responsive viewport inspection, and browser download UX require a real browser session and are not claimed as automated tests. The backend health route, static page availability, PDF content, and JavaScript syntax were verified locally.
