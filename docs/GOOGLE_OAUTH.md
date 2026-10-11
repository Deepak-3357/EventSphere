# Google OAuth status

The experimental React Google OAuth flow has been retired with `frontend-app/`.
There is no React preview callback or preview redirect URL to configure.

Do not add React-specific callback URLs, Vite environment variables, Google
client secrets, or preview origins to the repository. Any future OAuth work
must be designed for the original static frontend in `frontend/`, reviewed
against the existing Supabase session model, and configured with exact URLs
only in the appropriate provider dashboards.

Google client secrets and Supabase service-role credentials must never be
stored in this repository or exposed to browser JavaScript.
