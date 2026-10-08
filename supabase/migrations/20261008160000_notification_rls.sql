-- Phase 6: user-owned notification read/update policy.

drop policy if exists notifications_select_own on public.notifications;
drop policy if exists notifications_update_own on public.notifications;

create policy notifications_select_own
    on public.notifications for select
    to authenticated
    using (user_id = auth.uid());

create policy notifications_update_own
    on public.notifications for update
    to authenticated
    using (user_id = auth.uid())
    with check (user_id = auth.uid());

-- INSERT remains server-side through the Flask notification service.
