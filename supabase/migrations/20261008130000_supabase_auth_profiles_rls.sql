-- Phase 3: Supabase Auth integration, profile synchronization, and initial RLS.
-- This migration contains no credentials.

-- Phase 2 shipped fake standalone profiles before Auth existed. NOT VALID preserves
-- those development rows while enforcing the relationship for all new rows.
do $$
begin
    if not exists (
        select 1
        from pg_constraint
        where conname = 'profiles_auth_user_fk'
          and conrelid = 'public.profiles'::regclass
    ) then
        alter table public.profiles
            add constraint profiles_auth_user_fk
            foreign key (id) references auth.users(id) on delete restrict not valid;
    end if;
end $$;

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
    requested_year integer;
begin
    requested_year := case
        when (new.raw_user_meta_data ->> 'year') ~ '^[1-8]$'
            then (new.raw_user_meta_data ->> 'year')::integer
        else null
    end;

    insert into public.profiles (
        id, full_name, email, phone, role, department, year
    ) values (
        new.id,
        coalesce(nullif(trim(new.raw_user_meta_data ->> 'full_name'), ''), new.email, 'EventSphere User'),
        new.email,
        nullif(trim(new.raw_user_meta_data ->> 'phone'), ''),
        'student',
        nullif(trim(new.raw_user_meta_data ->> 'department'), ''),
        requested_year
    )
    on conflict (id) do nothing;

    return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
    after insert on auth.users
    for each row execute procedure public.handle_new_user();

create or replace function public.current_user_role()
returns text
language sql
stable
security definer
set search_path = public
as $$
    select role from public.profiles where id = auth.uid();
$$;

alter table public.profiles enable row level security;
alter table public.events enable row level security;
alter table public.registrations enable row level security;
alter table public.notifications enable row level security;

drop policy if exists profiles_select_own on public.profiles;
create policy profiles_select_own
    on public.profiles for select
    to authenticated
    using (id = auth.uid());

drop policy if exists profiles_update_own_non_role on public.profiles;
create policy profiles_update_own_non_role
    on public.profiles for update
    to authenticated
    using (id = auth.uid())
    with check (id = auth.uid() and role = public.current_user_role());

drop policy if exists events_foundation_select on public.events;
create policy events_foundation_select
    on public.events for select
    to authenticated
    using (
        status = 'published'
        or organizer_id = auth.uid()
        or public.current_user_role() = 'admin'
    );

drop policy if exists registrations_select_own on public.registrations;
create policy registrations_select_own
    on public.registrations for select
    to authenticated
    using (student_id = auth.uid());

drop policy if exists notifications_select_own on public.notifications;
create policy notifications_select_own
    on public.notifications for select
    to authenticated
    using (user_id = auth.uid());
