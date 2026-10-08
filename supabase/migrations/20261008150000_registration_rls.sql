-- Phase 5: registration visibility policies. No credentials or destructive resets.

drop policy if exists registrations_select_own on public.registrations;
drop policy if exists registrations_select_owner_or_admin on public.registrations;

create policy registrations_select_owner_or_admin
    on public.registrations for select
    to authenticated
    using (
        student_id = auth.uid()
        or public.current_user_role() = 'admin'
        or exists (
            select 1
            from public.events event_row
            where event_row.id = registrations.event_id
              and event_row.organizer_id = auth.uid()
        )
    );

-- Registration writes remain server-side in Flask for Phase 5. The API uses
-- the PostgreSQL connection layer and performs the same ownership checks.
