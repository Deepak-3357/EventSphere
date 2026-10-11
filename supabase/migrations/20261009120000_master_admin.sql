-- EventSphere: exactly one server-designated Master Admin.
-- The partial unique index enforces at most one designation under concurrency.
-- Provisioning is explicit and never performed by public registration.

alter table public.profiles
    add column if not exists is_master_admin boolean not null default false;

create unique index if not exists profiles_single_master_admin_idx
    on public.profiles (is_master_admin)
    where is_master_admin = true;

comment on column public.profiles.is_master_admin is
    'Trusted server-side designation. Only a guarded local provisioning process may set this true.';
