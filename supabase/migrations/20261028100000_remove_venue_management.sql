-- EventSphere: remove Venue Management while preserving historical event rows.
-- This migration is forward-only. It does not delete venue rows or event rows.

begin;

-- Remove booking data and policies created by the retired feature.
do $$
begin
    if to_regclass('public.venue_bookings') is not null then
        drop policy if exists venue_bookings_select on public.venue_bookings;
    end if;
end $$;
drop table if exists public.venue_bookings;

-- Keep historical venue UUIDs on events as nullable legacy data, but remove the
-- foreign-key dependency so new events no longer require a venue catalogue.
do $$
declare
    constraint_name text;
begin
    if to_regclass('public.venues') is not null then
        for constraint_name in
            select conname
            from pg_constraint
            where conrelid = 'public.events'::regclass
              and confrelid = 'public.venues'::regclass
        loop
            execute format('alter table public.events drop constraint %I', constraint_name);
        end loop;
    end if;
end $$;

alter table public.events alter column venue_id drop not null;
drop index if exists public.idx_events_venue_id;

-- Preserve the four existing venue rows as a read-only legacy archive. The
-- application no longer references this table, and no rows are deleted.
do $$
begin
    if to_regclass('public.venues') is not null
       and to_regclass('public.legacy_event_venues') is null then
        alter table public.venues rename to legacy_event_venues;
    end if;
end $$;

alter table if exists public.legacy_event_venues
    drop column if exists is_active,
    drop column if exists venue_type,
    drop column if exists updated_at;

drop index if exists public.venues_name_ci_unique;
drop index if exists public.venues_active_type_idx;

-- btree_gist is only removable when no exclusion constraint remains. If other
-- application objects use it, leave the shared extension in place.
do $$
begin
    if exists (select 1 from pg_extension where extname = 'btree_gist')
       and not exists (select 1 from pg_constraint where contype = 'x') then
        drop extension btree_gist;
    end if;
end $$;

commit;
