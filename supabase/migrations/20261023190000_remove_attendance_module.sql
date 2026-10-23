-- Forward migration: Permanently remove the attendance module.
-- Generated as part of attendance feature deprecation.
--
-- CAUTION:
-- Do NOT execute this migration on production without explicit administrative approval.
-- Executing this migration will permanently remove all historical attendance records,
-- attendance codes, and attendance rate-limiting attempt history.
--
-- Preserved objects:
-- - public.registrations (all student registrations, statuses, timestamps)
-- - public.events (including manual lifecycle columns: started_at, started_by, ended_at, ended_by)
-- - public.event_lifecycle_audit (audit trail for manual start/end/unpublish)
-- - public.profiles (all student, organizer, and admin accounts)
-- - public.od_letters (all OD letters and verification tokens)
-- - public.notifications (all student and organizer notifications)
-- - public.teams, public.team_members (team participation data)
-- - public.categories, public.venues, public.event_faqs

-- 1. Drop attendance-code rate-limiting table, indexes, and RLS policies
drop table if exists public.attendance_code_attempts cascade;

-- 2. Drop attendance-codes table, constraints, indexes, and RLS policies
drop table if exists public.attendance_codes cascade;

-- 3. Drop attendance check-in table, constraints, indexes, and RLS policies
drop table if exists public.attendance cascade;
