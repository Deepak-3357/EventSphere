# Local test accounts

The seed data contains development-only profile rows for:

- `admin@example.test` — admin profile
- `rohan.organizer@example.test` — organizer profile
- `diya.organizer@example.test` — organizer profile

The requested `Admin@gmail.com` Master Admin is not seeded and is never silently designated.
No password is committed or claimed as provisioned until the guarded local setup is run.

These rows do not contain passwords and do not by themselves create Supabase Auth identities. Do not add passwords, service-role keys, or database credentials to this repository.

## Safe setup

1. In the Supabase Dashboard, open **Authentication → Users** and create each email with a temporary password known only to the local tester. Disable email confirmation for the local development project, or confirm each email through the configured test mailbox.
2. Copy each Auth user UUID from the Users table.
3. Compare it with the corresponding profile UUID in **Table Editor → profiles**. If a profile was seeded with a different UUID, use a trusted server-side database session to update the profile ID and its dependent rows, or recreate the development profile before adding application data. Never expose the service-role key or database password to the browser.
4. Set only the `profiles.role` value (`organizer` or `admin`) through a trusted administrative/database process. The public registration form always creates `student` profiles and never accepts a role.
5. Sign in through `/login/`, then verify `/api/auth/me` returns the expected role and that the matching dashboard loads.

For repeatable local setup, create an ignored `.env.local` containing `EVENTSPHERE_DEV_MODE=1`, `EVENTSPHERE_PROVISION_CONFIRM=CREATE_LOCAL_TEST_ACCOUNTS`, `SUPABASE_SERVICE_ROLE_KEY`, `EVENTSPHERE_ADMIN_TEST_PASSWORD`, and `EVENTSPHERE_ORGANIZER_TEST_PASSWORD`, then run:

```powershell
python backend\scripts\provision_local_test_accounts.py
```

The script is guarded against production mode, is idempotent, updates existing Auth passwords, auto-confirms these development users, preserves event/registration/attendance rows while re-homing the legacy seed profiles, and retains legacy profile rows as non-Auth fixture placeholders. It never prints credentials. It also refuses a second Master Admin and rejects passwords shorter than six characters; the requested `1234` value is therefore not accepted by this setup. Supabase’s Admin Auth API requires a server-only service-role key; the official Supabase documentation explicitly warns not to expose it in browser code. If you do not want to place that key in local ignored configuration, use the Dashboard procedure above instead, then designate the Master Admin through a trusted local database session. The application Master Admin panel is available only when the database profile has `is_master_admin=true`; ordinary admins do not receive user-management access.
