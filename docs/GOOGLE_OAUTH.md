# Student Google OAuth setup

The React preview supports Google OAuth only through the existing Supabase
client. The browser never receives a Google client secret and no `VITE_*`
secret is required.

## Supabase dashboard setup

1. In Supabase Authentication providers, enable Google.
2. Configure the Google OAuth client ID and secret in Supabase, not in this
   repository.
3. Add the Supabase-provided callback URL to the Google Cloud OAuth client.
4. Add the application callback URLs to Supabase's URL configuration:

```text
http://127.0.0.1:5173/auth/callback/
https://<preview-static-site>.onrender.com/auth/callback/
https://eventsphere-395t.onrender.com/auth/callback/
```

Use the exact deployed origins and paths. Do not add wildcard redirect URLs.

## Authorization model

The existing `handle_new_user` trigger creates a profile with role `student`
for a new Supabase Auth user. The React callback then calls Flask
`/api/auth/me`; the backend-loaded profile remains authoritative. The client
does not send or choose a role. Existing organizer/admin/Master Admin profiles
are not changed. If a non-student profile reaches the student OAuth callback,
the client signs out and directs the user to the authorized email/password
flow.

No database migration is required for this phase if the existing Auth/profile
trigger migration is applied. Verify that the trigger exists in the target
Supabase project before enabling the provider.

## Local testing

```powershell
cd frontend-app
npm run dev
```

Open `http://127.0.0.1:5173/login/`. Test email/password first, then Google
after configuring the provider and exact redirect URL. Test cancellation,
provider errors, refresh on `/auth/callback/`, missing profiles, and a
privileged test account separately.

The frontend uses a same-origin allowlist for student return paths and rejects
external or admin destinations. Tokens and OAuth authorization data are never
written to logs.
