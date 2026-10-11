-- EventSphere enhancement: participation settings, facilities, and organizer FAQs.
-- Forward-only and safe for existing events: defaults preserve individual registration.

alter table public.events
    add column if not exists participation_mode text not null default 'individual'
        check (participation_mode in ('individual', 'team', 'both')),
    add column if not exists min_team_size integer,
    add column if not exists max_team_size integer,
    add column if not exists eligibility text,
    add column if not exists registration_instructions text,
    add column if not exists facilities jsonb not null default '{}'::jsonb;

do $$
begin
    if not exists (select 1 from pg_constraint where conname = 'events_team_size_valid' and conrelid = 'public.events'::regclass) then
        alter table public.events add constraint events_team_size_valid check (
            (participation_mode = 'individual' and min_team_size is null and max_team_size is null)
            or (participation_mode in ('team', 'both') and min_team_size between 2 and 100
                and max_team_size between min_team_size and 100)
        );
    end if;
end $$;

create table if not exists public.event_faqs (
    id uuid primary key default gen_random_uuid(),
    event_id uuid not null references public.events(id) on delete cascade,
    question text not null check (length(trim(question)) between 3 and 300),
    answer text not null check (length(trim(answer)) between 1 and 3000),
    position integer not null default 0 check (position >= 0),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists event_faqs_event_position_idx on public.event_faqs(event_id, position, created_at);
alter table public.event_faqs enable row level security;

drop policy if exists event_faqs_public_read on public.event_faqs;
create policy event_faqs_public_read on public.event_faqs for select using (
    exists (select 1 from public.events e where e.id = event_id and e.status = 'published')
    or exists (select 1 from public.events e where e.id = event_id and e.organizer_id = auth.uid())
    or exists (select 1 from public.profiles p where p.id = auth.uid() and p.role = 'admin')
);

-- FAQ writes stay in Flask, where ownership and input validation are enforced.
