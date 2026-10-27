-- EventSphere: consolidate the uncommitted faculty venue role into organizer.
-- Do not modify existing profile rows automatically. Before validating this
-- constraint in a database that contains faculty rows, an operator must review
-- and explicitly migrate those account IDs to role = 'organizer'.

alter table public.profiles
    drop constraint if exists profiles_role_check;

-- NOT VALID keeps existing rows readable while preventing any new unsupported
-- role values. After approved account migration, run:
--   update public.profiles set role = 'organizer' where role = 'faculty';
--   alter table public.profiles validate constraint profiles_role_check;
alter table public.profiles
    add constraint profiles_role_check
    check (role in ('student', 'organizer', 'admin')) not valid;

drop policy if exists venue_bookings_select on public.venue_bookings;
create policy venue_bookings_select
    on public.venue_bookings for select
    to authenticated
    using (
        requester_id = auth.uid()
        or public.current_user_role() in ('organizer', 'admin')
    );
