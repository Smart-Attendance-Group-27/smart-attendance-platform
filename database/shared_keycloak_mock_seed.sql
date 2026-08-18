-- UniAttend shared Keycloak mock data
--
-- Purpose:
--   Creates a small shared-development dataset around the shared Keycloak users
--   in mockDetails.txt. This seed is intentionally separate from the base demo
--   seed so it can be applied without rebuilding or replacing existing Supabase
--   data.
--
-- Notes:
--   * Authentication is handled by Keycloak; password_hash stays NULL.
--   * Existing rows are not overwritten. The first student email already exists
--     in the demo seed, so this file reuses that user/profile.
--   * No QR tokens/batches are inserted. Use the QR creation API to create those.
--   * Session times are refreshed only for the new shared mock sessions created
--     by this file, so they remain visible for mobile/manual testing.

BEGIN;
SET LOCAL TIME ZONE 'UTC';

-- ============================================================
-- 1. Identity users from shared Keycloak
-- ============================================================

INSERT INTO identity.users (
  id, email, password_hash, account_status, failed_login_attempts,
  locked_until, last_login_at, must_change_password, password_changed_at,
  created_by, created_at, updated_at, keycloak_user_id
)
VALUES
  (
    '52000000-0000-0000-0000-000000000002',
    '230737r@student.uniattend.test',
    NULL, 'active', 0, NULL, NULL, false, NULL,
    NULL, now(), now(),
    '8fb03922-5c9c-4734-a823-e3f4932925eb'
  ),
  (
    '52000000-0000-0000-0000-000000000003',
    'lecutere01@lectuere.uniattend.test',
    NULL, 'active', 0, NULL, NULL, false, NULL,
    NULL, now(), now(),
    '325e2cdd-71b6-417e-bb6e-3c990ac7aace'
  ),
  (
    '52000000-0000-0000-0000-000000000004',
    'lecutere02@lectuere.uniattend.test',
    NULL, 'active', 0, NULL, NULL, false, NULL,
    NULL, now(), now(),
    '22bd9602-6061-4869-9766-83f7ec03b24a'
  ),
  (
    '52000000-0000-0000-0000-000000000005',
    'admin01@lectuere.uniattend.test',
    NULL, 'active', 0, NULL, NULL, false, NULL,
    NULL, now(), now(),
    'e66d4bf5-ed74-4f55-8ca8-6754199605db'
  )
ON CONFLICT (email) DO NOTHING;

INSERT INTO identity.user_roles (user_id, role_id, assigned_by, assigned_at, is_active)
SELECT u.id, r.id, NULL, now(), true
FROM identity.users AS u
JOIN identity.roles AS r ON r.role_code = 'STUDENT'
WHERE u.email IN (
  '230736r@student.uniattend.test',
  '230737r@student.uniattend.test'
)
ON CONFLICT (user_id, role_id) DO NOTHING;

INSERT INTO identity.user_roles (user_id, role_id, assigned_by, assigned_at, is_active)
SELECT u.id, r.id, NULL, now(), true
FROM identity.users AS u
JOIN identity.roles AS r ON r.role_code = 'LECTURER'
WHERE u.email IN (
  'lecutere01@lectuere.uniattend.test',
  'lecutere02@lectuere.uniattend.test'
)
ON CONFLICT (user_id, role_id) DO NOTHING;

INSERT INTO identity.user_roles (user_id, role_id, assigned_by, assigned_at, is_active)
SELECT u.id, r.id, NULL, now(), true
FROM identity.users AS u
JOIN identity.roles AS r ON r.role_code = 'ADMINISTRATOR'
WHERE u.email = 'admin01@lectuere.uniattend.test'
ON CONFLICT (user_id, role_id) DO NOTHING;

-- ============================================================
-- 2. Academic profiles
-- ============================================================

INSERT INTO academic.student_profiles (
  id, user_id, registration_number, first_name, middle_name, last_name,
  department_id, intake_year, current_semester, profile_status,
  last_synced_at, created_at, updated_at
)
SELECT
  '53000000-0000-0000-0000-000000000002',
  u.id,
  '230737R',
  'Anura',
  NULL,
  'Kumara',
  '31000000-0000-0000-0000-000000000001',
  2023,
  5,
  'active',
  now(),
  now(),
  now()
FROM identity.users AS u
WHERE u.email = '230737r@student.uniattend.test'
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO academic.lecturer_profiles (
  id, user_id, employee_number, first_name, middle_name, last_name,
  department_id, designation, profile_status,
  last_synced_at, created_at, updated_at
)
SELECT *
FROM (
  SELECT
    '54000000-0000-0000-0000-000000000001'::uuid AS id,
    u.id AS user_id,
    'lecturer01'::varchar AS employee_number,
    'Indika'::varchar AS first_name,
    NULL::varchar AS middle_name,
    'Perera'::varchar AS last_name,
    '31000000-0000-0000-0000-000000000001'::uuid AS department_id,
    'Senior Lecturer'::varchar AS designation,
    'active'::varchar AS profile_status,
    now() AS last_synced_at,
    now() AS created_at,
    now() AS updated_at
  FROM identity.users AS u
  WHERE u.email = 'lecutere01@lectuere.uniattend.test'

  UNION ALL

  SELECT
    '54000000-0000-0000-0000-000000000002'::uuid,
    u.id,
    'lecturer02'::varchar,
    'Dulani'::varchar,
    NULL::varchar,
    'Meedeniya'::varchar,
    '31000000-0000-0000-0000-000000000001'::uuid,
    'Lecturer'::varchar,
    'active'::varchar,
    now(),
    now(),
    now()
  FROM identity.users AS u
  WHERE u.email = 'lecutere02@lectuere.uniattend.test'
) AS lecturer_rows
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO academic.administrator_profiles (
  id, user_id, first_name, middle_name, last_name, department_id,
  administrative_scope, profile_status, created_at, updated_at
)
SELECT
  '55000000-0000-0000-0000-000000000001',
  u.id,
  'Kamal',
  NULL,
  'Perera',
  '31000000-0000-0000-0000-000000000001',
  'department',
  'active',
  now(),
  now()
FROM identity.users AS u
WHERE u.email = 'admin01@lectuere.uniattend.test'
ON CONFLICT (user_id) DO NOTHING;

-- ============================================================
-- 3. Shared mock courses and offerings
-- ============================================================

INSERT INTO academic.courses (
  id, course_code, course_name, department_id, credits,
  course_description, status, last_synced_at, created_at, updated_at
)
VALUES
  (
    '56000000-0000-0000-0000-000000000001',
    'MOCK401',
    'Mobile Attendance Systems',
    '31000000-0000-0000-0000-000000000001',
    3,
    'Shared-development mock course for mobile attendance and QR testing.',
    'active',
    now(),
    now(),
    now()
  ),
  (
    '56000000-0000-0000-0000-000000000002',
    'MOCK402',
    'Distributed Backend Services',
    '31000000-0000-0000-0000-000000000001',
    3,
    'Shared-development mock course for FastAPI, Redis and service integration testing.',
    'active',
    now(),
    now(),
    now()
  ),
  (
    '56000000-0000-0000-0000-000000000003',
    'MOCK403',
    'Attendance Analytics and Notifications',
    '31000000-0000-0000-0000-000000000001',
    2,
    'Shared-development mock course for attendance reports and notifications.',
    'active',
    now(),
    now(),
    now()
  )
ON CONFLICT (course_code) DO NOTHING;

INSERT INTO academic.course_offerings (
  id, lms_course_offering_id, course_id, semester_id, batch_year,
  course_type, attendance_threshold, status,
  last_synced_at, created_at, updated_at
)
VALUES
  (
    '57000000-0000-0000-0000-000000000001',
    '97500000-0000-0000-0000-000000000001',
    '56000000-0000-0000-0000-000000000001',
    '35000000-0000-0000-0000-000000000001',
    2023,
    'lecture',
    80,
    'active',
    now(),
    now(),
    now()
  ),
  (
    '57000000-0000-0000-0000-000000000002',
    '97500000-0000-0000-0000-000000000002',
    '56000000-0000-0000-0000-000000000002',
    '35000000-0000-0000-0000-000000000001',
    2023,
    'lecture',
    80,
    'active',
    now(),
    now(),
    now()
  ),
  (
    '57000000-0000-0000-0000-000000000003',
    '97500000-0000-0000-0000-000000000003',
    '56000000-0000-0000-0000-000000000003',
    '35000000-0000-0000-0000-000000000001',
    2023,
    'lecture',
    75,
    'active',
    now(),
    now(),
    now()
  )
ON CONFLICT (id) DO NOTHING;

INSERT INTO academic.course_lecturers (
  id, course_offering_id, lecturer_id, lecturer_role, assigned_at, last_synced_at
)
VALUES
  (
    '58000000-0000-0000-0000-000000000001',
    '57000000-0000-0000-0000-000000000001',
    '54000000-0000-0000-0000-000000000001',
    'primary',
    now(),
    now()
  ),
  (
    '58000000-0000-0000-0000-000000000002',
    '57000000-0000-0000-0000-000000000002',
    '54000000-0000-0000-0000-000000000001',
    'primary',
    now(),
    now()
  ),
  (
    '58000000-0000-0000-0000-000000000003',
    '57000000-0000-0000-0000-000000000002',
    '54000000-0000-0000-0000-000000000002',
    'co_lecturer',
    now(),
    now()
  ),
  (
    '58000000-0000-0000-0000-000000000004',
    '57000000-0000-0000-0000-000000000003',
    '54000000-0000-0000-0000-000000000002',
    'primary',
    now(),
    now()
  )
ON CONFLICT (course_offering_id, lecturer_id) DO NOTHING;

-- ============================================================
-- 4. Student enrolments
-- ============================================================

INSERT INTO academic.course_enrolments (
  id, course_offering_id, student_id, enrolment_status,
  enrolled_at, dropped_at, last_synced_at, created_at, updated_at
)
SELECT *
FROM (
  SELECT
    '59000000-0000-0000-0000-000000000001'::uuid AS id,
    '57000000-0000-0000-0000-000000000001'::uuid AS course_offering_id,
    sp.id AS student_id,
    'enrolled'::varchar AS enrolment_status,
    now() AS enrolled_at,
    NULL::timestamptz AS dropped_at,
    now() AS last_synced_at,
    now() AS created_at,
    now() AS updated_at
  FROM academic.student_profiles AS sp
  JOIN identity.users AS u ON u.id = sp.user_id
  WHERE u.email = '230736r@student.uniattend.test'

  UNION ALL

  SELECT '59000000-0000-0000-0000-000000000002'::uuid, '57000000-0000-0000-0000-000000000002'::uuid, sp.id, 'enrolled'::varchar, now(), NULL::timestamptz, now(), now(), now()
  FROM academic.student_profiles AS sp
  JOIN identity.users AS u ON u.id = sp.user_id
  WHERE u.email = '230736r@student.uniattend.test'

  UNION ALL

  SELECT '59000000-0000-0000-0000-000000000003'::uuid, '57000000-0000-0000-0000-000000000003'::uuid, sp.id, 'enrolled'::varchar, now(), NULL::timestamptz, now(), now(), now()
  FROM academic.student_profiles AS sp
  JOIN identity.users AS u ON u.id = sp.user_id
  WHERE u.email = '230736r@student.uniattend.test'

  UNION ALL

  SELECT '59000000-0000-0000-0000-000000000004'::uuid, '57000000-0000-0000-0000-000000000001'::uuid, sp.id, 'enrolled'::varchar, now(), NULL::timestamptz, now(), now(), now()
  FROM academic.student_profiles AS sp
  JOIN identity.users AS u ON u.id = sp.user_id
  WHERE u.email = '230737r@student.uniattend.test'

  UNION ALL

  SELECT '59000000-0000-0000-0000-000000000005'::uuid, '57000000-0000-0000-0000-000000000002'::uuid, sp.id, 'enrolled'::varchar, now(), NULL::timestamptz, now(), now(), now()
  FROM academic.student_profiles AS sp
  JOIN identity.users AS u ON u.id = sp.user_id
  WHERE u.email = '230737r@student.uniattend.test'

  UNION ALL

  SELECT '59000000-0000-0000-0000-000000000006'::uuid, '57000000-0000-0000-0000-000000000003'::uuid, sp.id, 'enrolled'::varchar, now(), NULL::timestamptz, now(), now(), now()
  FROM academic.student_profiles AS sp
  JOIN identity.users AS u ON u.id = sp.user_id
  WHERE u.email = '230737r@student.uniattend.test'
) AS enrolment_rows
ON CONFLICT (course_offering_id, student_id) DO NOTHING;

-- ============================================================
-- 5. Timetable entries and active attendance sessions
-- ============================================================

INSERT INTO academic.timetable_entries (
  id, course_offering_id, classroom_id, day_of_week, start_time, end_time,
  course_type, valid_from, valid_until, status, created_by, created_at, updated_at
)
VALUES
  (
    '5a000000-0000-0000-0000-000000000001',
    '57000000-0000-0000-0000-000000000001',
    '33000000-0000-0000-0000-000000000001',
    EXTRACT(ISODOW FROM now())::smallint,
    '09:00',
    '11:00',
    'lecture',
    current_date - 7,
    current_date + 60,
    'active',
    (SELECT id FROM identity.users WHERE email = 'lecutere01@lectuere.uniattend.test'),
    now(),
    now()
  ),
  (
    '5a000000-0000-0000-0000-000000000002',
    '57000000-0000-0000-0000-000000000002',
    '33000000-0000-0000-0000-000000000002',
    EXTRACT(ISODOW FROM now())::smallint,
    '11:00',
    '13:00',
    'lecture',
    current_date - 7,
    current_date + 60,
    'active',
    (SELECT id FROM identity.users WHERE email = 'lecutere01@lectuere.uniattend.test'),
    now(),
    now()
  ),
  (
    '5a000000-0000-0000-0000-000000000003',
    '57000000-0000-0000-0000-000000000003',
    '33000000-0000-0000-0000-000000000003',
    EXTRACT(ISODOW FROM now())::smallint,
    '14:00',
    '16:00',
    'lecture',
    current_date - 7,
    current_date + 60,
    'active',
    (SELECT id FROM identity.users WHERE email = 'lecutere02@lectuere.uniattend.test'),
    now(),
    now()
  )
ON CONFLICT (id) DO NOTHING;

INSERT INTO attendance_session.sessions (
  id, course_offering_id, timetable_entry_id, timetable_exception_id, created_by,
  session_title, session_type, scheduled_start_at, scheduled_end_at,
  check_in_opens_at, check_in_closes_at, late_after_at, status,
  requires_face_verification, requires_geofence, requires_qr,
  activated_at, closed_at, cancelled_at, cancellation_reason,
  created_at, updated_at
)
VALUES
  (
    '5b000000-0000-0000-0000-000000000001',
    '57000000-0000-0000-0000-000000000001',
    '5a000000-0000-0000-0000-000000000001',
    NULL,
    (SELECT id FROM identity.users WHERE email = 'lecutere01@lectuere.uniattend.test'),
    'Shared Mock: Mobile Attendance Systems',
    'lecture',
    now() - INTERVAL '15 minutes',
    now() + INTERVAL '3 hours',
    now() - INTERVAL '10 minutes',
    now() + INTERVAL '2 hours',
    now() + INTERVAL '20 minutes',
    'active',
    true,
    true,
    true,
    now() - INTERVAL '10 minutes',
    NULL,
    NULL,
    NULL,
    now(),
    now()
  ),
  (
    '5b000000-0000-0000-0000-000000000002',
    '57000000-0000-0000-0000-000000000002',
    '5a000000-0000-0000-0000-000000000002',
    NULL,
    (SELECT id FROM identity.users WHERE email = 'lecutere01@lectuere.uniattend.test'),
    'Shared Mock: Distributed Backend Services',
    'lecture',
    now() - INTERVAL '15 minutes',
    now() + INTERVAL '3 hours',
    now() - INTERVAL '10 minutes',
    now() + INTERVAL '2 hours',
    now() + INTERVAL '20 minutes',
    'active',
    true,
    true,
    true,
    now() - INTERVAL '10 minutes',
    NULL,
    NULL,
    NULL,
    now(),
    now()
  ),
  (
    '5b000000-0000-0000-0000-000000000003',
    '57000000-0000-0000-0000-000000000003',
    '5a000000-0000-0000-0000-000000000003',
    NULL,
    (SELECT id FROM identity.users WHERE email = 'lecutere02@lectuere.uniattend.test'),
    'Shared Mock: Analytics and Notifications',
    'lecture',
    now() - INTERVAL '15 minutes',
    now() + INTERVAL '3 hours',
    now() - INTERVAL '10 minutes',
    now() + INTERVAL '2 hours',
    now() + INTERVAL '20 minutes',
    'active',
    true,
    true,
    true,
    now() - INTERVAL '10 minutes',
    NULL,
    NULL,
    NULL,
    now(),
    now()
  )
ON CONFLICT (id) DO UPDATE SET
  scheduled_start_at = EXCLUDED.scheduled_start_at,
  scheduled_end_at = EXCLUDED.scheduled_end_at,
  check_in_opens_at = EXCLUDED.check_in_opens_at,
  check_in_closes_at = EXCLUDED.check_in_closes_at,
  late_after_at = EXCLUDED.late_after_at,
  status = 'active',
  activated_at = EXCLUDED.activated_at,
  closed_at = NULL,
  cancelled_at = NULL,
  cancellation_reason = NULL,
  updated_at = now();

INSERT INTO attendance_session.session_geofences (
  session_id, accuracy_buffer_m, maximum_allowed_accuracy_m, created_at, updated_at
)
VALUES
  ('5b000000-0000-0000-0000-000000000001', 20, 100, now(), now()),
  ('5b000000-0000-0000-0000-000000000002', 20, 100, now(), now()),
  ('5b000000-0000-0000-0000-000000000003', 20, 100, now(), now())
ON CONFLICT (session_id) DO UPDATE SET
  accuracy_buffer_m = EXCLUDED.accuracy_buffer_m,
  maximum_allowed_accuracy_m = EXCLUDED.maximum_allowed_accuracy_m,
  updated_at = now();

INSERT INTO attendance_session.session_students (
  id, session_id, student_id, course_enrolment_id, created_at
)
SELECT *
FROM (
  SELECT '5c000000-0000-0000-0000-000000000001'::uuid, '5b000000-0000-0000-0000-000000000001'::uuid, ce.student_id, ce.id, now()
  FROM academic.course_enrolments AS ce
  JOIN academic.student_profiles AS sp ON sp.id = ce.student_id
  JOIN identity.users AS u ON u.id = sp.user_id
  WHERE ce.course_offering_id = '57000000-0000-0000-0000-000000000001'
    AND u.email = '230736r@student.uniattend.test'

  UNION ALL

  SELECT '5c000000-0000-0000-0000-000000000002'::uuid, '5b000000-0000-0000-0000-000000000001'::uuid, ce.student_id, ce.id, now()
  FROM academic.course_enrolments AS ce
  JOIN academic.student_profiles AS sp ON sp.id = ce.student_id
  JOIN identity.users AS u ON u.id = sp.user_id
  WHERE ce.course_offering_id = '57000000-0000-0000-0000-000000000001'
    AND u.email = '230737r@student.uniattend.test'

  UNION ALL

  SELECT '5c000000-0000-0000-0000-000000000003'::uuid, '5b000000-0000-0000-0000-000000000002'::uuid, ce.student_id, ce.id, now()
  FROM academic.course_enrolments AS ce
  JOIN academic.student_profiles AS sp ON sp.id = ce.student_id
  JOIN identity.users AS u ON u.id = sp.user_id
  WHERE ce.course_offering_id = '57000000-0000-0000-0000-000000000002'
    AND u.email = '230736r@student.uniattend.test'

  UNION ALL

  SELECT '5c000000-0000-0000-0000-000000000004'::uuid, '5b000000-0000-0000-0000-000000000002'::uuid, ce.student_id, ce.id, now()
  FROM academic.course_enrolments AS ce
  JOIN academic.student_profiles AS sp ON sp.id = ce.student_id
  JOIN identity.users AS u ON u.id = sp.user_id
  WHERE ce.course_offering_id = '57000000-0000-0000-0000-000000000002'
    AND u.email = '230737r@student.uniattend.test'

  UNION ALL

  SELECT '5c000000-0000-0000-0000-000000000005'::uuid, '5b000000-0000-0000-0000-000000000003'::uuid, ce.student_id, ce.id, now()
  FROM academic.course_enrolments AS ce
  JOIN academic.student_profiles AS sp ON sp.id = ce.student_id
  JOIN identity.users AS u ON u.id = sp.user_id
  WHERE ce.course_offering_id = '57000000-0000-0000-0000-000000000003'
    AND u.email = '230736r@student.uniattend.test'

  UNION ALL

  SELECT '5c000000-0000-0000-0000-000000000006'::uuid, '5b000000-0000-0000-0000-000000000003'::uuid, ce.student_id, ce.id, now()
  FROM academic.course_enrolments AS ce
  JOIN academic.student_profiles AS sp ON sp.id = ce.student_id
  JOIN identity.users AS u ON u.id = sp.user_id
  WHERE ce.course_offering_id = '57000000-0000-0000-0000-000000000003'
    AND u.email = '230737r@student.uniattend.test'
) AS session_student_rows
ON CONFLICT (session_id, student_id) DO NOTHING;

-- ============================================================
-- 6. Lightweight notification data for the student notification UI
-- ============================================================

INSERT INTO notification.notification_types (
  code, description, default_in_app_enabled, default_push_enabled,
  default_email_enabled, user_configurable, is_active, created_at, updated_at
)
VALUES
  ('ATTENDANCE_SESSION_STARTED', 'Attendance session has started', true, true, false, true, true, now(), now()),
  ('ATTENDANCE_RISK', 'Attendance percentage needs attention', true, true, true, true, true, now(), now()),
  ('QR_REQUIRED', 'QR verification is required for an active session', true, true, false, true, true, now(), now())
ON CONFLICT (code) DO NOTHING;

INSERT INTO notification.notifications (
  id, recipient_user_id, notification_type, title, body, priority,
  related_entity_type, related_entity_id, in_app_visible,
  scheduled_for, read_at, expires_at, created_at
)
SELECT *
FROM (
  SELECT
    '5d000000-0000-0000-0000-000000000001'::uuid,
    u.id,
    'QR_REQUIRED'::varchar,
    'QR verification is ready'::varchar,
    'Open the active Mobile Attendance Systems session and complete face + QR verification.'::text,
    'high'::varchar,
    'attendance_session'::varchar,
    '5b000000-0000-0000-0000-000000000001'::uuid,
    true,
    now(),
    NULL::timestamptz,
    now() + INTERVAL '1 day',
    now()
  FROM identity.users AS u
  WHERE u.email = '230736r@student.uniattend.test'

  UNION ALL

  SELECT
    '5d000000-0000-0000-0000-000000000002'::uuid,
    u.id,
    'ATTENDANCE_SESSION_STARTED'::varchar,
    'Backend Services lecture is live'::varchar,
    'The Distributed Backend Services attendance session is open for check-in.'::text,
    'normal'::varchar,
    'attendance_session'::varchar,
    '5b000000-0000-0000-0000-000000000002'::uuid,
    true,
    now(),
    NULL::timestamptz,
    now() + INTERVAL '1 day',
    now()
  FROM identity.users AS u
  WHERE u.email = '230737r@student.uniattend.test'
) AS notification_rows
ON CONFLICT (id) DO NOTHING;

COMMIT;
