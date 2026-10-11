-- EventSphere team registration model. Existing registrations remain individual.

create table if not exists public.teams (
    id uuid primary key default gen_random_uuid(),
    event_id uuid not null references public.events(id) on delete restrict,
    name text not null check (length(trim(name)) between 2 and 120),
    leader_id uuid not null references public.profiles(id) on delete restrict,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists teams_event_id_idx on public.teams(event_id);
create unique index if not exists teams_event_name_idx on public.teams(event_id, lower(name));

create table if not exists public.team_members (
    id uuid primary key default gen_random_uuid(),
    team_id uuid not null references public.teams(id) on delete cascade,
    student_id uuid references public.profiles(id) on delete restrict,
    full_name text not null check (length(trim(full_name)) between 2 and 160),
    email text not null check (length(trim(email)) > 3),
    department text,
    year integer check (year is null or year between 1 and 8),
    position integer not null check (position >= 0),
    created_at timestamptz not null default now(),
    unique (team_id, position)
);

create unique index if not exists team_members_email_idx on public.team_members(team_id, lower(email));
create index if not exists team_members_student_id_idx on public.team_members(student_id);

alter table public.registrations
    add column if not exists participation_type text not null default 'individual'
        check (participation_type in ('individual', 'team')),
    add column if not exists team_id uuid references public.teams(id) on delete restrict;

alter table public.registrations
    drop constraint if exists registrations_team_consistency;
alter table public.registrations
    add constraint registrations_team_consistency check (
        (participation_type = 'individual' and team_id is null)
        or (participation_type = 'team' and team_id is not null)
    );

alter table public.teams enable row level security;
alter table public.team_members enable row level security;

drop policy if exists teams_select_participants on public.teams;
create policy teams_select_participants on public.teams for select to authenticated using (
    leader_id = auth.uid()
    or exists (select 1 from public.team_members tm where tm.team_id = teams.id and tm.student_id = auth.uid())
    or exists (select 1 from public.events e join public.profiles p on p.id = auth.uid() where e.id = teams.event_id and (e.organizer_id = auth.uid() or p.role = 'admin'))
);

drop policy if exists team_members_select_participants on public.team_members;
create policy team_members_select_participants on public.team_members for select to authenticated using (
    student_id = auth.uid()
    or exists (select 1 from public.teams t where t.id = team_id and t.leader_id = auth.uid())
    or exists (select 1 from public.teams t join public.events e on e.id = t.event_id join public.profiles p on p.id = auth.uid() where t.id = team_id and (e.organizer_id = auth.uid() or p.role = 'admin'))
);

-- All team writes remain in the Flask service after event ownership and role checks.
