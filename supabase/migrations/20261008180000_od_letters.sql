-- Phase 8: EventSphere-generated OD letter metadata.

create table if not exists public.od_letters (
    id uuid primary key default gen_random_uuid(),
    registration_id uuid not null references public.registrations(id) on delete restrict,
    student_id uuid not null references public.profiles(id) on delete restrict,
    event_id uuid not null references public.events(id) on delete restrict,
    letter_number text not null unique,
    issued_at timestamptz not null default now(),
    status text not null default 'generated' check (status in ('generated', 'cancelled')),
    created_at timestamptz not null default now(),
    constraint od_letters_one_active_per_registration unique (registration_id)
);

create index if not exists od_letters_student_id_idx on public.od_letters(student_id);
create index if not exists od_letters_event_id_idx on public.od_letters(event_id);
alter table public.od_letters enable row level security;

drop policy if exists od_letters_select_own on public.od_letters;
create policy od_letters_select_own on public.od_letters for select to authenticated
    using (student_id = auth.uid());

-- OD creation and updates are server-side only. Verification uses a signed token.
