# React preview retired

The experimental React frontend previously lived in `frontend-app/`. It has
been retired and is no longer part of EventSphere. Do not create a Render
Static Site for it or change the production service to use it.

The production frontend is the original static site in `frontend/`. Keep its
existing Render Static Site configuration and publish directory unchanged.
The Flask backend remains a separate service, with its existing production
origin and exact CORS allowlist.

The original frontend uses the existing Supabase session model, Flask bearer
authentication, QR attendance flow, six-digit attendance codes, and OD-letter
workflow. Keep signing secrets, database credentials, and service-role keys
server-side.
