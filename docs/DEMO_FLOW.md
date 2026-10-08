# EventSphere demo flow

1. Start the Flask API and frontend static server.
2. Sign in as a student, browse a published event, and register.
3. Show the registration confirmation notification and student dashboard counters.
4. Open the registration, display the signed event pass, and generate/download the OD PDF.
5. Open the PDF verification QR or verification URL and show its minimal valid result.
6. Sign in as the event organizer, show the organizer-scoped dashboard and event analytics.
7. Open the attendance scanner, scan the student pass, and show the attendance report update.
8. Sign in as admin and show platform-wide counters, category analytics, and attendance.

Architecture explanation: Browser HTML/CSS/Bootstrap/vanilla JavaScript → Fetch API → Flask REST API and service layer → Supabase PostgreSQL, with Supabase Auth bearer-token verification.

If camera access is unavailable during a presentation, use the signed payload from the event-pass API in the check-in API smoke test; do not claim that as a camera test.
