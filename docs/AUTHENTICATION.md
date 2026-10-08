# EventSphere authentication

## Supabase Auth

Email/password authentication is handled by Supabase Auth. EventSphere does not hash passwords, create Flask sessions, or store passwords in `profiles`.

In the Supabase dashboard, enable the Email provider and add the local frontend URL (`http://127.0.0.1:5500`) to the project’s allowed URL/redirect configuration before testing the browser flow.

The browser receives the public Supabase URL and publishable key from `GET /api/config`. The database password and any service-role credential remain server-side in the ignored `.env` file.

## Registration

`/register/` collects full name, email, password, confirmation, department, year, and optional phone. It calls Supabase `signUp` with profile metadata. It has no role selector; public registrations always become students.

The Phase 3 migration installs an `after insert` trigger on `auth.users`. The trigger creates one `profiles` row using the Auth UUID and assigns `student` regardless of client metadata. Organizer and admin roles must be promoted through a controlled administrative/database process.

## Login, logout, and sessions

`/login/` calls Supabase `signInWithPassword`. After sign-in, the client calls `/api/auth/me`, reads the server-loaded profile role, and redirects to the matching placeholder dashboard. Logout calls Supabase `signOut` and returns to `/login/`.

Supabase manages the browser session and access token. The frontend uses `getSession()` after page refresh and never stores passwords or manually creates tokens. Protected dashboard pages redirect to `/login/` when no session exists.

## Auth user and profile relationship

```text
auth.users.id  ── 1:1 ── profiles.id
```

The foreign key is `NOT VALID` because Phase 2 already contained fake standalone development profiles. It still enforces the relationship for new rows while preserving those legacy seed records. The Auth trigger handles all new users.

## Backend verification and RBAC

Protected Flask routes require `Authorization: Bearer <access_token>`. The reusable `require_auth` decorator calls Supabase Auth’s `/auth/v1/user` endpoint to validate the token, then loads the profile by the verified Auth UUID. The backend never trusts a user ID or role from request data.

Validation endpoints:

- `GET /api/auth/me`
- `GET /api/auth/student-test`
- `GET /api/auth/organizer-test`
- `GET /api/auth/admin-test`

`require_role` checks the role retrieved from `profiles`. These endpoints are temporary Phase 3 checks; application APIs belong to later phases.

## RLS foundation

RLS is enabled on `profiles`, `events`, `registrations`, and `notifications`.

- Profiles: users can read/update their own profile, but updates must preserve the current role.
- Events: authenticated users can read published events, their own organizer events, or admin-visible events.
- Registrations: users can read their own registrations.
- Notifications: users can read their own notifications.
- Direct client writes are not enabled yet; event and registration authorization will be expanded later.

## Development and testing

```powershell
py -m pip install -r backend\requirements.txt
py backend\scripts\apply_migrations.py
py -m unittest discover -s tests -v
```

Use fake `.example.test` accounts only. Do not put development passwords in source control. If email confirmation is enabled in Supabase, registration displays a confirmation message before login.
