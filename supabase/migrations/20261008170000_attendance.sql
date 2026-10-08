-- Phase 7: server-created attendance records and organizer/admin read access.

create table if not exists public.attendance (
    id uuid primary key default gen_random_uuid(),
    registration_id uuid not null references public.registrations(id) on delete restrict,
    event_id uuid not null references public.events(id) on delete restrict,
    student_id uuid not null references public.profiles(id) on delete restrict,
    checked_in_at timestamptz not null default now(),
    status text not null default 'present' check (status in ('present', 'cancelled')),
    scanned_by uuid not null references public.profiles(id) on delete restrict,
    created_at timestamptz not null default now(),
    constraint attendance_one_per_registration unique (registration_id)
);

create index if not exists attendance_event_id_idx on public.attendance(event_id);
create index if not exists attendance_student_id_idx on public.attendance(student_id);
create index if not exists attendance_registration_id_idx on public.attendance(registration_id);
create index if not exists attendance_scanned_by_idx on public.attendance(scanned_by);
create index if not exists attendance_checked_in_at_idx on public.attendance(checked_in_at);

alter table public.attendance enable row level security;

drop policy if exists attendance_select_authorized on public.attendance;
create policy attendance_select_authorized
    on public.attendance for select
    to authenticated
    using (
        student_id = auth.uid()
        or exists (
            select 1 from public.profiles p
            where p.id = auth.uid() and p.role = 'admin'
        )
        or exists (
            select 1 from public.events e
            where e.id = attendance.event_id and e.organizer_id = auth.uid()
        )
    );

-- There are deliberately no client insert/update/delete policies. The backend
-- service creates records only after validating the signed QR payload.
