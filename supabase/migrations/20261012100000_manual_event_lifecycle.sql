-- EventSphere: manual event lifecycle (Start/End) controls.
-- Additive only: no existing column is modified or dropped, no data is migrated.
-- The publication `status` column and its CHECK constraint are untouched.

alter table public.events
    add column if not exists started_at timestamptz,
    add column if not exists started_by uuid references public.profiles(id) on delete set null,
    add column if not exists ended_at timestamptz,
    add column if not exists ended_by uuid references public.profiles(id) on delete set null;

-- A manual end can only exist after the event has been started.
alter table public.events
    drop constraint if exists events_lifecycle_order_check;
alter table public.events
    add constraint events_lifecycle_order_check
    check (ended_at is null or started_at is not null and ended_at >= started_at);

create index if not exists events_lifecycle_state_idx on public.events (status, started_at, ended_at);

-- Minimal audit trail for manual lifecycle changes.
create table if not exists public.event_lifecycle_audit (
    id uuid primary key default gen_random_uuid(),
    event_id uuid not null references public.events(id) on delete cascade,
    action text not null check (action in ('manual_start', 'manual_end', 'manual_unpublish')),
    actor_id uuid not null references public.profiles(id) on delete restrict,
    action_at timestamptz not null default now()
);

create index if not exists event_lifecycle_audit_event_idx on public.event_lifecycle_audit (event_id, action_at);

alter table public.event_lifecycle_audit enable row level security;

drop policy if exists event_lifecycle_audit_select on public.event_lifecycle_audit;
create policy event_lifecycle_audit_select
    on public.event_lifecycle_audit for select
    to authenticated
    using (
        exists (
            select 1 from public.events e
            where e.id = event_lifecycle_audit.event_id and e.organizer_id = auth.uid()
        )
        or exists (
            select 1 from public.profiles p
            where p.id = auth.uid() and p.role = 'admin'
        )
    );

-- Writes are backend-only, matching every other service-reserved table.
