-- Deterministic, fake development data. No passwords or Auth users are inserted.

insert into profiles (id, full_name, email, role, department, year) values
    ('00000000-0000-0000-0000-000000000001', 'Aarav Menon', 'aarav.student@example.test', 'student', 'Computer Science', 2),
    ('00000000-0000-0000-0000-000000000002', 'Mira Shah', 'mira.student@example.test', 'student', 'Information Technology', 3),
    ('00000000-0000-0000-0000-000000000003', 'Rohan Iyer', 'rohan.organizer@example.test', 'organizer', 'Computer Science', null),
    ('00000000-0000-0000-0000-000000000004', 'Diya Nair', 'diya.organizer@example.test', 'organizer', 'Student Activities', null),
    ('00000000-0000-0000-0000-000000000005', 'System Administrator', 'admin@example.test', 'admin', 'Administration', null)
on conflict (id) do nothing;

insert into categories (id, name, description) values
    ('10000000-0000-0000-0000-000000000001', 'Technical', 'Technology talks, competitions, and demonstrations.'),
    ('10000000-0000-0000-0000-000000000002', 'Cultural', 'Arts, music, and cultural celebrations.'),
    ('10000000-0000-0000-0000-000000000003', 'Sports', 'Sports meets and wellness activities.'),
    ('10000000-0000-0000-0000-000000000004', 'Workshop', 'Hands-on learning sessions.'),
    ('10000000-0000-0000-0000-000000000005', 'Seminar', 'Academic and professional seminars.')
on conflict (id) do nothing;

insert into events (id, title, description, category_id, organizer_id, event_date, start_time, end_time, capacity, registration_deadline, status) values
    ('30000000-0000-0000-0000-000000000001', 'Campus Hack Day', 'A collaborative day of prototyping and problem solving.', '10000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000003', '2026-11-14', '09:00', '17:00', 80, '2026-11-13 18:00:00+05:30', 'published'),
    ('30000000-0000-0000-0000-000000000002', 'Intercollegiate Cultural Evening', 'An evening of student performances and creative showcases.', '10000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-000000000004', '2026-12-05', '17:00', '20:00', 450, '2026-12-04 18:00:00+05:30', 'pending'),
    ('30000000-0000-0000-0000-000000000003', 'Research Careers Seminar', 'A practical discussion about research pathways and internships.', '10000000-0000-0000-0000-000000000005', '00000000-0000-0000-0000-000000000003', '2026-11-28', '14:00', '16:00', 120, '2026-11-27 18:00:00+05:30', 'draft')
on conflict (id) do nothing;

insert into registrations (id, event_id, student_id, status) values
    ('40000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000001', 'registered'),
    ('40000000-0000-0000-0000-000000000002', '30000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000002', 'registered')
on conflict (id) do nothing;

insert into notifications (id, user_id, title, message, type) values
    ('50000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000001', 'Registration confirmed', 'Your place at Campus Hack Day is confirmed.', 'registration'),
    ('50000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-000000000002', 'Registration confirmed', 'Your place at Campus Hack Day is confirmed.', 'registration')
on conflict (id) do nothing;
