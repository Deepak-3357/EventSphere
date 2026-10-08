# OD letters

Students can generate one EventSphere OD letter for each active registration in a published event. The student registration page links to the OD workflow, which creates/reuses metadata and offers a PDF download.

## APIs

- `POST /api/registrations/<registration_id>/od-letter` creates or reuses an OD record for the authenticated owner.
- `GET /api/registrations/<registration_id>/od-letter` returns the authenticated student's record.
- `GET /api/od-letters/<letter_id>/download` returns an A4 PDF for the owner.
- `GET /api/od-letters/<letter_id>/verify?token=...` publicly verifies a signed token and returns only letter number, issue date, event, event date, and status.

PDF creation is in `backend/app/services/od_letter_service.py` using ReportLab and qrcode. The document is explicitly EventSphere-generated and uses only fields available in `profiles`, `events`, `venues`, and `registrations`; unavailable institutional register-number data is not invented. The PDF includes a signed verification QR.

The `od_letters` migration enforces one metadata row per registration, UUID foreign keys, unique letter numbers, and RLS for student reads. Creation/download authorization is enforced again by Flask. A cancelled registration makes an existing letter unavailable for download; its verification record remains available and reports its stored status, preserving history without presenting a usable current duty letter.
