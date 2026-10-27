# Venue management and role migration

Venue management is available to `organizer` and `admin` accounts. Organizers
can view the venue calendar, check availability, create bookings, and manage
their own bookings. Administrators can also create or deactivate venues and
view or cancel bookings across the system. Students cannot access venue
management endpoints.

The original venue-management migration is retained as migration history. The
follow-up migration `20261027193000_remove_faculty_role.sql` removes `faculty`
from the active profile role constraint and replaces the venue-booking policy
with organizer/admin access. It is intentionally `NOT VALID` at first so a
database containing legacy faculty rows is not made unavailable during a
deployment.

Before validating that constraint in a maintenance window, an authorized
administrator must review any legacy faculty accounts and explicitly migrate
them, for example:

```sql
update public.profiles
set role = 'organizer'
where role = 'faculty';

alter table public.profiles
validate constraint profiles_role_check;
```

Review the affected accounts and obtain the required application approval
before running either statement. This repository does not run production SQL
automatically.

Booking integrity remains enforced by the venue-booking exclusion constraint,
row locks, event-slot conflict checks, and row-level security. Organizer
booking reads are ownership-scoped; admin reads are global.
