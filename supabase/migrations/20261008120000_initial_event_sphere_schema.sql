-- EventSphere Phase 2 schema. Credentials never belong in migration files.

create table if not exists profiles (
    id uuid primary key default gen_random_uuid(),
    full_name text not null check (length(trim(full_name)) > 0),
    email text not null unique check (length(trim(email)) > 3),
    phone text,
    role text not null default 'student' check (role in ('student', 'organizer', 'admin')),
    department text,
    year integer check (year is null or year between 1 and 8),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists categories (
    id uuid primary key default gen_random_uuid(),
    name text not null unique check (length(trim(name)) > 0),
    description text,
    created_at timestamptz not null default now()
);

create table if not exists venues (
    id uuid primary key default gen_random_uuid(),
    name text not null unique check (length(trim(name)) > 0),
    location text not null check (length(trim(location)) > 0),
    capacity integer not null check (capacity > 0),
    created_at timestamptz not null default now()
);

create table if not exists events (
    id uuid primary key default gen_random_uuid(),
    title text not null check (length(trim(title)) > 0),
    description text,
    category_id uuid not null references categories(id) on delete restrict,
    organizer_id uuid not null references profiles(id) on delete restrict,
    venue_id uuid not null references venues(id) on delete restrict,
    event_date date not null,
    start_time time not null,
    end_time time not null,
    capacity integer not null check (capacity > 0),
    registration_deadline timestamptz not null,
    status text not null default 'draft' check (status in ('draft', 'pending', 'published', 'cancelled', 'completed')),
    image_url text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    check (end_time > start_time)
);

create table if not exists registrations (
    id uuid primary key default gen_random_uuid(),
    event_id uuid not null references events(id) on delete restrict,
    student_id uuid not null references profiles(id) on delete restrict,
    registered_at timestamptz not null default now(),
    status text not null default 'registered' check (status in ('registered', 'cancelled')),
    unique (event_id, student_id)
);

create table if not exists notifications (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references profiles(id) on delete restrict,
    title text not null check (length(trim(title)) > 0),
    message text not null check (length(trim(message)) > 0),
    type text not null check (type in ('registration', 'event_update', 'cancellation', 'reminder', 'system')),
    is_read boolean not null default false,
    created_at timestamptz not null default now()
);

create index if not exists idx_events_category_id on events(category_id);
create index if not exists idx_events_organizer_id on events(organizer_id);
create index if not exists idx_events_venue_id on events(venue_id);
create index if not exists idx_events_date_status on events(event_date, status);
create index if not exists idx_registrations_event_id on registrations(event_id);
create index if not exists idx_registrations_student_id on registrations(student_id);
create index if not exists idx_notifications_user_id_created_at on notifications(user_id, created_at desc);
