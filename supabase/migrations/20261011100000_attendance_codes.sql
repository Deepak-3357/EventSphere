-- EventSphere Phase 2: event-scoped attendance codes.
-- Plaintext codes are never stored. code_hash is used for lookup and
-- code_ciphertext is encrypted at rest for the owning student event pass.

create table if not exists public.attendance_codes (
    id uuid primary key default gen_random_uuid(),
    registration_id uuid not null references public.registrations(id) on delete restrict,
    event_id uuid not null references public.events(id) on delete restrict,
    code_hash text not null,
    code_ciphertext text not null,
    active boolean not null default true,
    issued_at timestamptz not null default now(),
    revoked_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint attendance_codes_one_per_registration unique (registration_id),
    constraint attendance_codes_event_hash_unique unique (event_id, code_hash),
    constraint attendance_codes_active_revoked_check check (active or revoked_at is not null)
);

create index if not exists attendance_codes_event_active_idx on public.attendance_codes(event_id, active);
create index if not exists attendance_codes_registration_idx on public.attendance_codes(registration_id);

create table if not exists public.attendance_code_attempts (
    organizer_id uuid not null references public.profiles(id) on delete cascade,
    event_id uuid not null references public.events(id) on delete cascade,
    window_started_at timestamptz not null default now(),
    failed_attempts integer not null default 0 check (failed_attempts >= 0),
    locked_until timestamptz,
    updated_at timestamptz not null default now(),
    primary key (organizer_id, event_id)
);

alter table public.attendance_codes enable row level security;
alter table public.attendance_code_attempts enable row level security;

drop policy if exists attendance_codes_select_owner on public.attendance_codes;
create policy attendance_codes_select_owner
    on public.attendance_codes for select
    to authenticated
    using (
        exists (
            select 1 from public.registrations r
            where r.id = attendance_codes.registration_id and r.student_id = auth.uid()
        )
        or exists (
            select 1 from public.profiles p
            where p.id = auth.uid() and p.role = 'admin'
        )
        or exists (
            select 1 from public.events e
            where e.id = attendance_codes.event_id and e.organizer_id = auth.uid()
        )
    );

-- Attendance code writes are backend-only, just like attendance writes.
