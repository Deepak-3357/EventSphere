-- EventSphere Step 1: venue management and concurrency-safe bookings.
-- Apply this migration in a development Supabase project before deploying the
-- backend code. The application uses Asia/Kolkata as the campus timezone.

create extension if not exists btree_gist;

do $$
begin
    alter table public.profiles drop constraint if exists profiles_role_check;
    alter table public.profiles
        add constraint profiles_role_check
        check (role in ('student', 'organizer', 'faculty', 'admin'));
exception when duplicate_object then
    null;
end $$;

alter table public.venues
    add column if not exists is_active boolean not null default true;

create table if not exists public.venue_bookings (
    id uuid primary key default gen_random_uuid(),
    venue_id uuid not null references public.venues(id) on delete restrict,
    requester_id uuid not null references public.profiles(id) on delete restrict,
    event_id uuid references public.events(id) on delete set null,
    title text not null check (length(trim(title)) between 1 and 200),
    start_at timestamptz not null,
    end_at timestamptz not null,
    status text not null default 'confirmed' check (status in ('confirmed', 'cancelled')),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    check (end_at > start_at)
);

create index if not exists venue_bookings_venue_start_idx
    on public.venue_bookings (venue_id, start_at);
create index if not exists venue_bookings_requester_idx
    on public.venue_bookings (requester_id, created_at desc);
create index if not exists venue_bookings_event_idx
    on public.venue_bookings (event_id);

alter table public.venue_bookings
    drop constraint if exists venue_bookings_no_overlap;
alter table public.venue_bookings
    add constraint venue_bookings_no_overlap
    exclude using gist (
        venue_id with =,
        tstzrange(start_at, end_at, '[)') with &&
    ) where (status = 'confirmed');

alter table public.venue_bookings enable row level security;

drop policy if exists venue_bookings_select on public.venue_bookings;
create policy venue_bookings_select
    on public.venue_bookings for select
    to authenticated
    using (
        requester_id = auth.uid()
        or public.current_user_role() in ('faculty', 'admin')
    );

-- Booking writes remain backend-only, matching the existing service-role API.
-- Direct client writes therefore cannot bypass server validation or ownership.
