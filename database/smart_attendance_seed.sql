-- UniAttend demo seed data
-- Prerequisite: run database/smart_attendance_db_clean.sql first.
-- Designed for a fresh application database and safe to rerun with the same fixed UUIDs.
--
-- Conventions used by this seed:
--   * status values are lowercase (active, enrolled, etc.)
--   * day_of_week: 1 = Monday ... 7 = Sunday
--   * classroom coordinates are DUMMY TEST COORDINATES; replace before geofence testing
--   * password_hash is NULL because authentication will later be handled by Keycloak
--   * no QR batches/tokens are inserted; the QR creation API should create them
--   * no face embeddings or attendance verification results are fabricated

BEGIN;
SET LOCAL TIME ZONE 'UTC';

-- ============================================================
-- 1. Identity configuration: roles and permissions
-- ============================================================

INSERT INTO identity.roles (id, role_code, description, created_at)
VALUES
  ('10000000-0000-0000-0000-000000000001', 'STUDENT', 'Student mobile-application user', now()),
  ('10000000-0000-0000-0000-000000000002', 'LECTURER', 'Lecturer web-dashboard user', now()),
  ('10000000-0000-0000-0000-000000000003', 'ADMINISTRATOR', 'University attendance-platform administrator', now())
ON CONFLICT (id) DO UPDATE SET
  role_code = EXCLUDED.role_code,
  description = EXCLUDED.description;

INSERT INTO identity.permissions (id, permission_code, description, created_at)
VALUES
  ('11000000-0000-0000-0000-000000000001', 'PROFILE_VIEW_OWN', 'View own profile', now()),
  ('11000000-0000-0000-0000-000000000002', 'ACADEMIC_VIEW_OWN', 'View own courses and timetable', now()),
  ('11000000-0000-0000-0000-000000000003', 'ATTENDANCE_CHECK_IN', 'Perform initial attendance check-in', now()),
  ('11000000-0000-0000-0000-000000000004', 'QR_VERIFY', 'Submit a QR verification response', now()),
  ('11000000-0000-0000-0000-000000000005', 'ATTENDANCE_SESSION_MANAGE', 'Create and manage attendance sessions', now()),
  ('11000000-0000-0000-0000-000000000006', 'QR_SESSION_MANAGE', 'Create and close lecturer-triggered QR sessions', now()),
  ('11000000-0000-0000-0000-000000000007', 'ATTENDANCE_REPORT_VIEW', 'View class attendance reports', now()),
  ('11000000-0000-0000-0000-000000000008', 'ACADEMIC_DATA_MANAGE', 'Manage academic master data', now()),
  ('11000000-0000-0000-0000-000000000009', 'USER_ACCOUNT_MANAGE', 'Manage platform user accounts', now())
ON CONFLICT (id) DO UPDATE SET
  permission_code = EXCLUDED.permission_code,
  description = EXCLUDED.description;

-- Student permissions
INSERT INTO identity.role_permissions (role_id, permission_id, assigned_at)
VALUES
  ('10000000-0000-0000-0000-000000000001', '11000000-0000-0000-0000-000000000001', now()),
  ('10000000-0000-0000-0000-000000000001', '11000000-0000-0000-0000-000000000002', now()),
  ('10000000-0000-0000-0000-000000000001', '11000000-0000-0000-0000-000000000003', now()),
  ('10000000-0000-0000-0000-000000000001', '11000000-0000-0000-0000-000000000004', now())
ON CONFLICT (role_id, permission_id) DO UPDATE SET assigned_at = EXCLUDED.assigned_at;

-- Lecturer permissions
INSERT INTO identity.role_permissions (role_id, permission_id, assigned_at)
VALUES
  ('10000000-0000-0000-0000-000000000002', '11000000-0000-0000-0000-000000000001', now()),
  ('10000000-0000-0000-0000-000000000002', '11000000-0000-0000-0000-000000000005', now()),
  ('10000000-0000-0000-0000-000000000002', '11000000-0000-0000-0000-000000000006', now()),
  ('10000000-0000-0000-0000-000000000002', '11000000-0000-0000-0000-000000000007', now())
ON CONFLICT (role_id, permission_id) DO UPDATE SET assigned_at = EXCLUDED.assigned_at;

-- Administrator receives every seeded permission.
INSERT INTO identity.role_permissions (role_id, permission_id, assigned_at)
SELECT
  '10000000-0000-0000-0000-000000000003'::uuid,
  p.id,
  now()
FROM identity.permissions p
WHERE p.id IN (
  '11000000-0000-0000-0000-000000000001',
  '11000000-0000-0000-0000-000000000002',
  '11000000-0000-0000-0000-000000000003',
  '11000000-0000-0000-0000-000000000004',
  '11000000-0000-0000-0000-000000000005',
  '11000000-0000-0000-0000-000000000006',
  '11000000-0000-0000-0000-000000000007',
  '11000000-0000-0000-0000-000000000008',
  '11000000-0000-0000-0000-000000000009'
)
ON CONFLICT (role_id, permission_id) DO UPDATE SET assigned_at = EXCLUDED.assigned_at;

-- ============================================================
-- 2. Platform users
-- ============================================================

-- Administrator must be inserted first because other users refer to it as created_by.
INSERT INTO identity.users (
  id, email, password_hash, account_status, failed_login_attempts,
  locked_until, last_login_at, must_change_password, password_changed_at,
  created_by, created_at, updated_at
)
VALUES (
  '20000000-0000-0000-0000-000000000001',
  'admin@uniattend.test',
  NULL,
  'active',
  0,
  NULL,
  NULL,
  false,
  NULL,
  NULL,
  now(),
  now()
)
ON CONFLICT (id) DO UPDATE SET
  email = EXCLUDED.email,
  account_status = EXCLUDED.account_status,
  updated_at = now();

-- Three lecturers and six students.
INSERT INTO identity.users (
  id, email, password_hash, account_status, failed_login_attempts,
  locked_until, last_login_at, must_change_password, password_changed_at,
  created_by, created_at, updated_at
)
VALUES
  ('20000000-0000-0000-0000-000000000002', 'n.perera@staff.uniattend.test', NULL, 'active', 0, NULL, NULL, false, NULL, '20000000-0000-0000-0000-000000000001', now(), now()),
  ('20000000-0000-0000-0000-000000000003', 'k.jayasinghe@staff.uniattend.test', NULL, 'active', 0, NULL, NULL, false, NULL, '20000000-0000-0000-0000-000000000001', now(), now()),
  ('20000000-0000-0000-0000-000000000004', 's.fernando@staff.uniattend.test', NULL, 'active', 0, NULL, NULL, false, NULL, '20000000-0000-0000-0000-000000000001', now(), now()),
  ('20000000-0000-0000-0000-000000000011', '230701a@student.uniattend.test', NULL, 'active', 0, NULL, NULL, false, NULL, '20000000-0000-0000-0000-000000000001', now(), now()),
  ('20000000-0000-0000-0000-000000000012', '230702b@student.uniattend.test', NULL, 'active', 0, NULL, NULL, false, NULL, '20000000-0000-0000-0000-000000000001', now(), now()),
  ('20000000-0000-0000-0000-000000000013', '230703c@student.uniattend.test', NULL, 'active', 0, NULL, NULL, false, NULL, '20000000-0000-0000-0000-000000000001', now(), now()),
  ('20000000-0000-0000-0000-000000000014', '230704d@student.uniattend.test', NULL, 'active', 0, NULL, NULL, false, NULL, '20000000-0000-0000-0000-000000000001', now(), now()),
  ('20000000-0000-0000-0000-000000000015', '230705e@student.uniattend.test', NULL, 'active', 0, NULL, NULL, false, NULL, '20000000-0000-0000-0000-000000000001', now(), now()),
  ('20000000-0000-0000-0000-000000000016', '230736r@student.uniattend.test', NULL, 'active', 0, NULL, NULL, false, NULL, '20000000-0000-0000-0000-000000000001', now(), now())
ON CONFLICT (id) DO UPDATE SET
  email = EXCLUDED.email,
  account_status = EXCLUDED.account_status,
  created_by = EXCLUDED.created_by,
  updated_at = now();

-- User-role assignments.
INSERT INTO identity.user_roles (user_id, role_id, assigned_by, assigned_at, is_active)
VALUES
  ('20000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000003', '20000000-0000-0000-0000-000000000001', now(), true),
  ('20000000-0000-0000-0000-000000000002', '10000000-0000-0000-0000-000000000002', '20000000-0000-0000-0000-000000000001', now(), true),
  ('20000000-0000-0000-0000-000000000003', '10000000-0000-0000-0000-000000000002', '20000000-0000-0000-0000-000000000001', now(), true),
  ('20000000-0000-0000-0000-000000000004', '10000000-0000-0000-0000-000000000002', '20000000-0000-0000-0000-000000000001', now(), true),
  ('20000000-0000-0000-0000-000000000011', '10000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000001', now(), true),
  ('20000000-0000-0000-0000-000000000012', '10000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000001', now(), true),
  ('20000000-0000-0000-0000-000000000013', '10000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000001', now(), true),
  ('20000000-0000-0000-0000-000000000014', '10000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000001', now(), true),
  ('20000000-0000-0000-0000-000000000015', '10000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000001', now(), true),
  ('20000000-0000-0000-0000-000000000016', '10000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000001', now(), true)
ON CONFLICT (user_id, role_id) DO UPDATE SET
  assigned_by = EXCLUDED.assigned_by,
  assigned_at = EXCLUDED.assigned_at,
  is_active = EXCLUDED.is_active;

-- ============================================================
-- 3. Externally sourced academic organization data
-- ============================================================

INSERT INTO academic.faculties (
  id, university_faculty_id, faculty_name, status,
  last_synced_at, created_at, updated_at
)
VALUES (
  '30000000-0000-0000-0000-000000000001',
  '90000000-0000-0000-0000-000000000001',
  'Faculty of Engineering',
  'active',
  now(), now(), now()
)
ON CONFLICT (id) DO UPDATE SET
  university_faculty_id = EXCLUDED.university_faculty_id,
  faculty_name = EXCLUDED.faculty_name,
  status = EXCLUDED.status,
  last_synced_at = now(),
  updated_at = now();

INSERT INTO academic.departments (
  id, university_department_id, faculty_id, department_name,
  status, last_synced_at, created_at, updated_at
)
VALUES
  ('31000000-0000-0000-0000-000000000001', '91000000-0000-0000-0000-000000000001', '30000000-0000-0000-0000-000000000001', 'Department of Computer Science and Engineering', 'active', now(), now(), now()),
  ('31000000-0000-0000-0000-000000000002', '91000000-0000-0000-0000-000000000002', '30000000-0000-0000-0000-000000000001', 'Department of Mathematics', 'active', now(), now(), now())
ON CONFLICT (id) DO UPDATE SET
  university_department_id = EXCLUDED.university_department_id,
  faculty_id = EXCLUDED.faculty_id,
  department_name = EXCLUDED.department_name,
  status = EXCLUDED.status,
  last_synced_at = now(),
  updated_at = now();

-- ============================================================
-- 4. Student, lecturer and administrator profiles
-- ============================================================

INSERT INTO academic.administrator_profiles (
  id, user_id, first_name, middle_name, last_name, department_id,
  administrative_scope, profile_status, created_at, updated_at
)
VALUES (
  '21000000-0000-0000-0000-000000000001',
  '20000000-0000-0000-0000-000000000001',
  'System', NULL, 'Administrator',
  '31000000-0000-0000-0000-000000000001',
  'university', 'active', now(), now()
)
ON CONFLICT (id) DO UPDATE SET
  user_id = EXCLUDED.user_id,
  first_name = EXCLUDED.first_name,
  last_name = EXCLUDED.last_name,
  department_id = EXCLUDED.department_id,
  administrative_scope = EXCLUDED.administrative_scope,
  profile_status = EXCLUDED.profile_status,
  updated_at = now();

INSERT INTO academic.lecturer_profiles (
  id, user_id, employee_number, first_name, middle_name, last_name,
  department_id, designation, profile_status,
  last_synced_at, created_at, updated_at
)
VALUES
  ('22000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000002', 'EMP-CSE-001', 'N.', NULL, 'Perera', '31000000-0000-0000-0000-000000000001', 'Senior Lecturer', 'active', now(), now(), now()),
  ('22000000-0000-0000-0000-000000000002', '20000000-0000-0000-0000-000000000003', 'EMP-CSE-002', 'K.', NULL, 'Jayasinghe', '31000000-0000-0000-0000-000000000001', 'Lecturer', 'active', now(), now(), now()),
  ('22000000-0000-0000-0000-000000000003', '20000000-0000-0000-0000-000000000004', 'EMP-MA-001', 'S.', NULL, 'Fernando', '31000000-0000-0000-0000-000000000002', 'Professor', 'active', now(), now(), now())
ON CONFLICT (id) DO UPDATE SET
  user_id = EXCLUDED.user_id,
  employee_number = EXCLUDED.employee_number,
  first_name = EXCLUDED.first_name,
  last_name = EXCLUDED.last_name,
  department_id = EXCLUDED.department_id,
  designation = EXCLUDED.designation,
  profile_status = EXCLUDED.profile_status,
  last_synced_at = now(),
  updated_at = now();

INSERT INTO academic.student_profiles (
  id, user_id, registration_number, first_name, middle_name, last_name,
  department_id, intake_year, current_semester, profile_status,
  last_synced_at, created_at, updated_at
)
VALUES
  ('23000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000011', '230701A', 'Amal', NULL, 'Perera', '31000000-0000-0000-0000-000000000001', 2023, 5, 'active', now(), now(), now()),
  ('23000000-0000-0000-0000-000000000002', '20000000-0000-0000-0000-000000000012', '230702B', 'Nimal', NULL, 'Silva', '31000000-0000-0000-0000-000000000001', 2023, 5, 'active', now(), now(), now()),
  ('23000000-0000-0000-0000-000000000003', '20000000-0000-0000-0000-000000000013', '230703C', 'Kavindu', NULL, 'Fernando', '31000000-0000-0000-0000-000000000001', 2023, 5, 'active', now(), now(), now()),
  ('23000000-0000-0000-0000-000000000004', '20000000-0000-0000-0000-000000000014', '230704D', 'Tharushi', NULL, 'Jayasinghe', '31000000-0000-0000-0000-000000000001', 2023, 5, 'active', now(), now(), now()),
  ('23000000-0000-0000-0000-000000000005', '20000000-0000-0000-0000-000000000015', '230705E', 'Dinithi', NULL, 'Peris', '31000000-0000-0000-0000-000000000001', 2023, 5, 'active', now(), now(), now()),
  ('23000000-0000-0000-0000-000000000006', '20000000-0000-0000-0000-000000000016', '230736R', 'Mahesh', NULL, 'Withanage', '31000000-0000-0000-0000-000000000001', 2023, 5, 'active', now(), now(), now())
ON CONFLICT (id) DO UPDATE SET
  user_id = EXCLUDED.user_id,
  registration_number = EXCLUDED.registration_number,
  first_name = EXCLUDED.first_name,
  last_name = EXCLUDED.last_name,
  department_id = EXCLUDED.department_id,
  intake_year = EXCLUDED.intake_year,
  current_semester = EXCLUDED.current_semester,
  profile_status = EXCLUDED.profile_status,
  last_synced_at = now(),
  updated_at = now();

-- ============================================================
-- 5. Campus/building/classroom data
-- ============================================================

INSERT INTO academic.buildings (id, building_name, status, created_at, updated_at)
VALUES
  ('32000000-0000-0000-0000-000000000001', 'Engineering Faculty Building', 'active', now(), now()),
  ('32000000-0000-0000-0000-000000000002', 'Applied Sciences Building', 'active', now(), now())
ON CONFLICT (id) DO UPDATE SET
  building_name = EXCLUDED.building_name,
  status = EXCLUDED.status,
  updated_at = now();

-- These are dummy coordinates for development only.
INSERT INTO academic.classrooms (
  id, building_id, classroom_code, floor_number, capacity,
  latitude, longitude, default_geofence_radius_m,
  status, created_at, updated_at
)
VALUES
  ('33000000-0000-0000-0000-000000000001', '32000000-0000-0000-0000-000000000001', 'LH-02', 1, 120, 6.796100, 79.900700, 40, 'active', now(), now()),
  ('33000000-0000-0000-0000-000000000002', '32000000-0000-0000-0000-000000000001', 'LAB-03', 2, 45, 6.796180, 79.900760, 25, 'active', now(), now()),
  ('33000000-0000-0000-0000-000000000003', '32000000-0000-0000-0000-000000000002', 'B4', 0, 80, 6.796300, 79.900950, 35, 'active', now(), now())
ON CONFLICT (id) DO UPDATE SET
  building_id = EXCLUDED.building_id,
  classroom_code = EXCLUDED.classroom_code,
  floor_number = EXCLUDED.floor_number,
  capacity = EXCLUDED.capacity,
  latitude = EXCLUDED.latitude,
  longitude = EXCLUDED.longitude,
  default_geofence_radius_m = EXCLUDED.default_geofence_radius_m,
  status = EXCLUDED.status,
  updated_at = now();

-- ============================================================
-- 6. Academic year, semester, courses and offerings
-- ============================================================

INSERT INTO academic.academic_years (
  id, lms_academic_year_id, start_date, end_date,
  status, last_synced_at, created_at, updated_at
)
VALUES (
  '34000000-0000-0000-0000-000000000001',
  '94000000-0000-0000-0000-000000000001',
  DATE '2026-01-01', DATE '2026-12-31',
  'active', now(), now(), now()
)
ON CONFLICT (id) DO UPDATE SET
  lms_academic_year_id = EXCLUDED.lms_academic_year_id,
  start_date = EXCLUDED.start_date,
  end_date = EXCLUDED.end_date,
  status = EXCLUDED.status,
  last_synced_at = now(),
  updated_at = now();

INSERT INTO academic.semesters (
  id, lms_semester_id, academic_year_id, semester_number,
  start_date, end_date, status,
  last_synced_at, created_at, updated_at
)
VALUES (
  '35000000-0000-0000-0000-000000000001',
  '95000000-0000-0000-0000-000000000001',
  '34000000-0000-0000-0000-000000000001',
  1,
  DATE '2026-07-01', DATE '2026-12-20',
  'active', now(), now(), now()
)
ON CONFLICT (id) DO UPDATE SET
  lms_semester_id = EXCLUDED.lms_semester_id,
  academic_year_id = EXCLUDED.academic_year_id,
  semester_number = EXCLUDED.semester_number,
  start_date = EXCLUDED.start_date,
  end_date = EXCLUDED.end_date,
  status = EXCLUDED.status,
  last_synced_at = now(),
  updated_at = now();

INSERT INTO academic.courses (
  id, course_code, course_name, department_id, credits,
  course_description, status, last_synced_at, created_at, updated_at
)
VALUES
  ('36000000-0000-0000-0000-000000000001', 'CS3203', 'Software Engineering Project', '31000000-0000-0000-0000-000000000001', 3, 'Team software engineering project covering requirements, design, implementation and testing.', 'active', now(), now(), now()),
  ('36000000-0000-0000-0000-000000000002', 'CS3052', 'Computer Security', '31000000-0000-0000-0000-000000000001', 3, 'Foundations of secure systems, cryptography and application security.', 'active', now(), now(), now()),
  ('36000000-0000-0000-0000-000000000003', 'MA3030', 'Operational Research', '31000000-0000-0000-0000-000000000002', 3, 'Optimization, linear programming and decision models.', 'active', now(), now(), now()),
  ('36000000-0000-0000-0000-000000000004', 'EN3204', 'Engineering Mathematics', '31000000-0000-0000-0000-000000000002', 3, 'Applied mathematics for engineering analysis.', 'active', now(), now(), now())
ON CONFLICT (id) DO UPDATE SET
  course_code = EXCLUDED.course_code,
  course_name = EXCLUDED.course_name,
  department_id = EXCLUDED.department_id,
  credits = EXCLUDED.credits,
  course_description = EXCLUDED.course_description,
  status = EXCLUDED.status,
  last_synced_at = now(),
  updated_at = now();

INSERT INTO academic.course_offerings (
  id, lms_course_offering_id, course_id, semester_id,
  batch_year, course_type, attendance_threshold,
  status, last_synced_at, created_at, updated_at
)
VALUES
  ('37000000-0000-0000-0000-000000000001', '97000000-0000-0000-0000-000000000001', '36000000-0000-0000-0000-000000000001', '35000000-0000-0000-0000-000000000001', 2023, 'core', 80, 'active', now(), now(), now()),
  ('37000000-0000-0000-0000-000000000002', '97000000-0000-0000-0000-000000000002', '36000000-0000-0000-0000-000000000002', '35000000-0000-0000-0000-000000000001', 2023, 'core', 80, 'active', now(), now(), now()),
  ('37000000-0000-0000-0000-000000000003', '97000000-0000-0000-0000-000000000003', '36000000-0000-0000-0000-000000000003', '35000000-0000-0000-0000-000000000001', 2023, 'core', 80, 'active', now(), now(), now()),
  ('37000000-0000-0000-0000-000000000004', '97000000-0000-0000-0000-000000000004', '36000000-0000-0000-0000-000000000004', '35000000-0000-0000-0000-000000000001', 2023, 'core', 80, 'active', now(), now(), now())
ON CONFLICT (id) DO UPDATE SET
  lms_course_offering_id = EXCLUDED.lms_course_offering_id,
  course_id = EXCLUDED.course_id,
  semester_id = EXCLUDED.semester_id,
  batch_year = EXCLUDED.batch_year,
  course_type = EXCLUDED.course_type,
  attendance_threshold = EXCLUDED.attendance_threshold,
  status = EXCLUDED.status,
  last_synced_at = now(),
  updated_at = now();

-- ============================================================
-- 7. Lecturer assignments
-- ============================================================

INSERT INTO academic.course_lecturers (
  id, course_offering_id, lecturer_id, lecturer_role,
  assigned_at, last_synced_at
)
VALUES
  ('38000000-0000-0000-0000-000000000001', '37000000-0000-0000-0000-000000000001', '22000000-0000-0000-0000-000000000001', 'primary', now(), now()),
  ('38000000-0000-0000-0000-000000000002', '37000000-0000-0000-0000-000000000002', '22000000-0000-0000-0000-000000000002', 'primary', now(), now()),
  ('38000000-0000-0000-0000-000000000003', '37000000-0000-0000-0000-000000000003', '22000000-0000-0000-0000-000000000003', 'primary', now(), now()),
  ('38000000-0000-0000-0000-000000000004', '37000000-0000-0000-0000-000000000004', '22000000-0000-0000-0000-000000000003', 'primary', now(), now())
ON CONFLICT (id) DO UPDATE SET
  course_offering_id = EXCLUDED.course_offering_id,
  lecturer_id = EXCLUDED.lecturer_id,
  lecturer_role = EXCLUDED.lecturer_role,
  assigned_at = EXCLUDED.assigned_at,
  last_synced_at = now();

-- ============================================================
-- 8. Student course enrolments (20 total)
-- ============================================================

INSERT INTO academic.course_enrolments (
  id, course_offering_id, student_id, enrolment_status,
  enrolled_at, dropped_at, last_synced_at, created_at, updated_at
)
VALUES
  -- All six students: CS3203
  ('39000000-0000-0000-0000-000000000001', '37000000-0000-0000-0000-000000000001', '23000000-0000-0000-0000-000000000001', 'enrolled', TIMESTAMPTZ '2026-06-20 00:00:00+00', NULL, now(), now(), now()),
  ('39000000-0000-0000-0000-000000000002', '37000000-0000-0000-0000-000000000001', '23000000-0000-0000-0000-000000000002', 'enrolled', TIMESTAMPTZ '2026-06-20 00:00:00+00', NULL, now(), now(), now()),
  ('39000000-0000-0000-0000-000000000003', '37000000-0000-0000-0000-000000000001', '23000000-0000-0000-0000-000000000003', 'enrolled', TIMESTAMPTZ '2026-06-20 00:00:00+00', NULL, now(), now(), now()),
  ('39000000-0000-0000-0000-000000000004', '37000000-0000-0000-0000-000000000001', '23000000-0000-0000-0000-000000000004', 'enrolled', TIMESTAMPTZ '2026-06-20 00:00:00+00', NULL, now(), now(), now()),
  ('39000000-0000-0000-0000-000000000005', '37000000-0000-0000-0000-000000000001', '23000000-0000-0000-0000-000000000005', 'enrolled', TIMESTAMPTZ '2026-06-20 00:00:00+00', NULL, now(), now(), now()),
  ('39000000-0000-0000-0000-000000000006', '37000000-0000-0000-0000-000000000001', '23000000-0000-0000-0000-000000000006', 'enrolled', TIMESTAMPTZ '2026-06-20 00:00:00+00', NULL, now(), now(), now()),

  -- All six students: CS3052
  ('39000000-0000-0000-0000-000000000007', '37000000-0000-0000-0000-000000000002', '23000000-0000-0000-0000-000000000001', 'enrolled', TIMESTAMPTZ '2026-06-20 00:00:00+00', NULL, now(), now(), now()),
  ('39000000-0000-0000-0000-000000000008', '37000000-0000-0000-0000-000000000002', '23000000-0000-0000-0000-000000000002', 'enrolled', TIMESTAMPTZ '2026-06-20 00:00:00+00', NULL, now(), now(), now()),
  ('39000000-0000-0000-0000-000000000009', '37000000-0000-0000-0000-000000000002', '23000000-0000-0000-0000-000000000003', 'enrolled', TIMESTAMPTZ '2026-06-20 00:00:00+00', NULL, now(), now(), now()),
  ('39000000-0000-0000-0000-000000000010', '37000000-0000-0000-0000-000000000002', '23000000-0000-0000-0000-000000000004', 'enrolled', TIMESTAMPTZ '2026-06-20 00:00:00+00', NULL, now(), now(), now()),
  ('39000000-0000-0000-0000-000000000011', '37000000-0000-0000-0000-000000000002', '23000000-0000-0000-0000-000000000005', 'enrolled', TIMESTAMPTZ '2026-06-20 00:00:00+00', NULL, now(), now(), now()),
  ('39000000-0000-0000-0000-000000000012', '37000000-0000-0000-0000-000000000002', '23000000-0000-0000-0000-000000000006', 'enrolled', TIMESTAMPTZ '2026-06-20 00:00:00+00', NULL, now(), now(), now()),

  -- First four students: MA3030
  ('39000000-0000-0000-0000-000000000013', '37000000-0000-0000-0000-000000000003', '23000000-0000-0000-0000-000000000001', 'enrolled', TIMESTAMPTZ '2026-06-20 00:00:00+00', NULL, now(), now(), now()),
  ('39000000-0000-0000-0000-000000000014', '37000000-0000-0000-0000-000000000003', '23000000-0000-0000-0000-000000000002', 'enrolled', TIMESTAMPTZ '2026-06-20 00:00:00+00', NULL, now(), now(), now()),
  ('39000000-0000-0000-0000-000000000015', '37000000-0000-0000-0000-000000000003', '23000000-0000-0000-0000-000000000003', 'enrolled', TIMESTAMPTZ '2026-06-20 00:00:00+00', NULL, now(), now(), now()),
  ('39000000-0000-0000-0000-000000000016', '37000000-0000-0000-0000-000000000003', '23000000-0000-0000-0000-000000000004', 'enrolled', TIMESTAMPTZ '2026-06-20 00:00:00+00', NULL, now(), now(), now()),

  -- Last four students: EN3204
  ('39000000-0000-0000-0000-000000000017', '37000000-0000-0000-0000-000000000004', '23000000-0000-0000-0000-000000000003', 'enrolled', TIMESTAMPTZ '2026-06-20 00:00:00+00', NULL, now(), now(), now()),
  ('39000000-0000-0000-0000-000000000018', '37000000-0000-0000-0000-000000000004', '23000000-0000-0000-0000-000000000004', 'enrolled', TIMESTAMPTZ '2026-06-20 00:00:00+00', NULL, now(), now(), now()),
  ('39000000-0000-0000-0000-000000000019', '37000000-0000-0000-0000-000000000004', '23000000-0000-0000-0000-000000000005', 'enrolled', TIMESTAMPTZ '2026-06-20 00:00:00+00', NULL, now(), now(), now()),
  ('39000000-0000-0000-0000-000000000020', '37000000-0000-0000-0000-000000000004', '23000000-0000-0000-0000-000000000006', 'enrolled', TIMESTAMPTZ '2026-06-20 00:00:00+00', NULL, now(), now(), now())
ON CONFLICT (id) DO UPDATE SET
  course_offering_id = EXCLUDED.course_offering_id,
  student_id = EXCLUDED.student_id,
  enrolment_status = EXCLUDED.enrolment_status,
  enrolled_at = EXCLUDED.enrolled_at,
  dropped_at = EXCLUDED.dropped_at,
  last_synced_at = now(),
  updated_at = now();

-- ============================================================
-- 9. Recurring timetable
-- ============================================================

INSERT INTO academic.timetable_entries (
  id, course_offering_id, classroom_id, day_of_week,
  start_time, end_time, course_type,
  valid_from, valid_until, status,
  created_by, created_at, updated_at
)
VALUES
  ('3a000000-0000-0000-0000-000000000001', '37000000-0000-0000-0000-000000000001', '33000000-0000-0000-0000-000000000001', 1, TIME '10:00:00', TIME '12:00:00', 'lecture', DATE '2026-07-01', DATE '2026-12-20', 'active', '20000000-0000-0000-0000-000000000001', now(), now()),
  ('3a000000-0000-0000-0000-000000000002', '37000000-0000-0000-0000-000000000001', '33000000-0000-0000-0000-000000000002', 5, TIME '14:00:00', TIME '16:00:00', 'lab', DATE '2026-07-01', DATE '2026-12-20', 'active', '20000000-0000-0000-0000-000000000001', now(), now()),
  ('3a000000-0000-0000-0000-000000000003', '37000000-0000-0000-0000-000000000002', '33000000-0000-0000-0000-000000000002', 2, TIME '08:00:00', TIME '10:00:00', 'lecture', DATE '2026-07-01', DATE '2026-12-20', 'active', '20000000-0000-0000-0000-000000000001', now(), now()),
  ('3a000000-0000-0000-0000-000000000004', '37000000-0000-0000-0000-000000000003', '33000000-0000-0000-0000-000000000003', 4, TIME '13:00:00', TIME '15:00:00', 'lecture', DATE '2026-07-01', DATE '2026-12-20', 'active', '20000000-0000-0000-0000-000000000001', now(), now()),
  ('3a000000-0000-0000-0000-000000000005', '37000000-0000-0000-0000-000000000004', '33000000-0000-0000-0000-000000000003', 3, TIME '10:00:00', TIME '12:00:00', 'lecture', DATE '2026-07-01', DATE '2026-12-20', 'active', '20000000-0000-0000-0000-000000000001', now(), now())
ON CONFLICT (id) DO UPDATE SET
  course_offering_id = EXCLUDED.course_offering_id,
  classroom_id = EXCLUDED.classroom_id,
  day_of_week = EXCLUDED.day_of_week,
  start_time = EXCLUDED.start_time,
  end_time = EXCLUDED.end_time,
  course_type = EXCLUDED.course_type,
  valid_from = EXCLUDED.valid_from,
  valid_until = EXCLUDED.valid_until,
  status = EXCLUDED.status,
  created_by = EXCLUDED.created_by,
  updated_at = now();

-- No timetable exceptions are seeded initially.

-- ============================================================
-- 10. Notification type configuration and defaults
-- ============================================================

INSERT INTO notification.notification_types (
  code, description,
  default_in_app_enabled, default_push_enabled, default_email_enabled,
  user_configurable, is_active, created_at, updated_at
)
VALUES
  ('ATTENDANCE_SESSION_OPENED', 'An attendance session is open for check-in', true, true, false, true, true, now(), now()),
  ('ATTENDANCE_RESULT', 'A student attendance result was recorded or changed', true, true, false, true, true, now(), now()),
  ('QR_SESSION_ACTIVE', 'A lecturer activated an optional QR presence check', true, true, false, true, true, now(), now()),
  ('UPCOMING_CLASS', 'Reminder for an upcoming class', true, true, false, true, true, now(), now()),
  ('GENERAL', 'General platform notification', true, false, false, true, true, now(), now())
ON CONFLICT (code) DO UPDATE SET
  description = EXCLUDED.description,
  default_in_app_enabled = EXCLUDED.default_in_app_enabled,
  default_push_enabled = EXCLUDED.default_push_enabled,
  default_email_enabled = EXCLUDED.default_email_enabled,
  user_configurable = EXCLUDED.user_configurable,
  is_active = EXCLUDED.is_active,
  updated_at = now();

-- Default notification preferences for all seeded users.
INSERT INTO notification.notification_preferences (
  user_id, notification_type,
  in_app_enabled, push_enabled, email_enabled, updated_at
)
SELECT
  u.id,
  nt.code,
  nt.default_in_app_enabled,
  nt.default_push_enabled,
  nt.default_email_enabled,
  now()
FROM identity.users u
CROSS JOIN notification.notification_types nt
WHERE u.id IN (
  '20000000-0000-0000-0000-000000000001',
  '20000000-0000-0000-0000-000000000002',
  '20000000-0000-0000-0000-000000000003',
  '20000000-0000-0000-0000-000000000004',
  '20000000-0000-0000-0000-000000000011',
  '20000000-0000-0000-0000-000000000012',
  '20000000-0000-0000-0000-000000000013',
  '20000000-0000-0000-0000-000000000014',
  '20000000-0000-0000-0000-000000000015',
  '20000000-0000-0000-0000-000000000016'
)
AND nt.code IN (
  'ATTENDANCE_SESSION_OPENED',
  'ATTENDANCE_RESULT',
  'QR_SESSION_ACTIVE',
  'UPCOMING_CLASS',
  'GENERAL'
)
ON CONFLICT (user_id, notification_type) DO UPDATE SET
  in_app_enabled = EXCLUDED.in_app_enabled,
  push_enabled = EXCLUDED.push_enabled,
  email_enabled = EXCLUDED.email_enabled,
  updated_at = now();

-- ============================================================
-- 11. Face-verification configuration placeholder
-- ============================================================

-- Deliberately inactive until the team finishes model/threshold evaluation.
INSERT INTO face_verification.verification_configs (
  id, similarity_threshold, is_active, configured_by,
  effective_from, created_at
)
VALUES (
  '50000000-0000-0000-0000-000000000001',
  0.50,
  false,
  '20000000-0000-0000-0000-000000000001',
  now(),
  now()
)
ON CONFLICT (id) DO UPDATE SET
  similarity_threshold = EXCLUDED.similarity_threshold,
  is_active = EXCLUDED.is_active,
  configured_by = EXCLUDED.configured_by,
  effective_from = EXCLUDED.effective_from;

-- ============================================================
-- 12. One active attendance session for QR API testing
-- ============================================================

-- Timestamps are relative to transaction start, so the session is active whenever
-- this seed is run. Rerunning the seed refreshes the test window.
INSERT INTO attendance_session.sessions (
  id, course_offering_id, timetable_entry_id, timetable_exception_id,
  created_by, session_title, session_type,
  scheduled_start_at, scheduled_end_at,
  check_in_opens_at, check_in_closes_at, late_after_at,
  status, requires_face_verification, requires_geofence, requires_qr,
  activated_at, closed_at, cancelled_at, cancellation_reason,
  created_at, updated_at
)
VALUES (
  '40000000-0000-0000-0000-000000000001',
  '37000000-0000-0000-0000-000000000001',
  '3a000000-0000-0000-0000-000000000001',
  NULL,
  '20000000-0000-0000-0000-000000000002',
  'Static QR API Test Lecture',
  'lecture',
  now() - INTERVAL '5 minutes',
  now() + INTERVAL '144 hours',
  now() - INTERVAL '2 minutes',
  now() + INTERVAL '144 minutes',
  now(),
  'active',
  true,
  true,
  false,
  now() - INTERVAL '2 minutes',
  NULL,
  NULL,
  NULL,
  now() - INTERVAL '5 minutes',
  now()
)
ON CONFLICT (id) DO UPDATE SET
  course_offering_id = EXCLUDED.course_offering_id,
  timetable_entry_id = EXCLUDED.timetable_entry_id,
  timetable_exception_id = EXCLUDED.timetable_exception_id,
  created_by = EXCLUDED.created_by,
  session_title = EXCLUDED.session_title,
  session_type = EXCLUDED.session_type,
  scheduled_start_at = EXCLUDED.scheduled_start_at,
  scheduled_end_at = EXCLUDED.scheduled_end_at,
  check_in_opens_at = EXCLUDED.check_in_opens_at,
  check_in_closes_at = EXCLUDED.check_in_closes_at,
  late_after_at = EXCLUDED.late_after_at,
  status = EXCLUDED.status,
  requires_face_verification = EXCLUDED.requires_face_verification,
  requires_geofence = EXCLUDED.requires_geofence,
  requires_qr = EXCLUDED.requires_qr,
  activated_at = EXCLUDED.activated_at,
  closed_at = NULL,
  cancelled_at = NULL,
  cancellation_reason = NULL,
  updated_at = now();

INSERT INTO attendance_session.session_geofences (
  session_id, accuracy_buffer_m, maximum_allowed_accuracy_m,
  created_at, updated_at
)
VALUES (
  '40000000-0000-0000-0000-000000000001',
  10,
  50,
  now(),
  now()
)
ON CONFLICT (session_id) DO UPDATE SET
  accuracy_buffer_m = EXCLUDED.accuracy_buffer_m,
  maximum_allowed_accuracy_m = EXCLUDED.maximum_allowed_accuracy_m,
  updated_at = now();

-- Snapshot the six students enrolled in CS3203 into the active session.
INSERT INTO attendance_session.session_students (
  id, session_id, student_id, course_enrolment_id, created_at
)
VALUES
  ('41000000-0000-0000-0000-000000000001', '40000000-0000-0000-0000-000000000001', '23000000-0000-0000-0000-000000000001', '39000000-0000-0000-0000-000000000001', now()),
  ('41000000-0000-0000-0000-000000000002', '40000000-0000-0000-0000-000000000001', '23000000-0000-0000-0000-000000000002', '39000000-0000-0000-0000-000000000002', now()),
  ('41000000-0000-0000-0000-000000000003', '40000000-0000-0000-0000-000000000001', '23000000-0000-0000-0000-000000000003', '39000000-0000-0000-0000-000000000003', now()),
  ('41000000-0000-0000-0000-000000000004', '40000000-0000-0000-0000-000000000001', '23000000-0000-0000-0000-000000000004', '39000000-0000-0000-0000-000000000004', now()),
  ('41000000-0000-0000-0000-000000000005', '40000000-0000-0000-0000-000000000001', '23000000-0000-0000-0000-000000000005', '39000000-0000-0000-0000-000000000005', now()),
  ('41000000-0000-0000-0000-000000000006', '40000000-0000-0000-0000-000000000001', '23000000-0000-0000-0000-000000000006', '39000000-0000-0000-0000-000000000006', now())
ON CONFLICT (id) DO UPDATE SET
  session_id = EXCLUDED.session_id,
  student_id = EXCLUDED.student_id,
  course_enrolment_id = EXCLUDED.course_enrolment_id;

-- Intentionally not populated:
--   attendance_session.qr_token_batches
--   attendance_session.qr_tokens
--   attendance_verification.* operational attempt/record tables
--   face_verification.face_profiles
--   face_verification.face_validation_attempts
--   notification.notifications / delivery_attempts / device_tokens
--   reporting.report_requests
--   audit.audit_logs

COMMIT;

-- ============================================================
-- Verification queries (read-only)
-- ============================================================

SELECT 'identity.users' AS table_name, count(*) AS row_count FROM identity.users
UNION ALL SELECT 'academic.student_profiles', count(*) FROM academic.student_profiles
UNION ALL SELECT 'academic.lecturer_profiles', count(*) FROM academic.lecturer_profiles
UNION ALL SELECT 'academic.courses', count(*) FROM academic.courses
UNION ALL SELECT 'academic.course_offerings', count(*) FROM academic.course_offerings
UNION ALL SELECT 'academic.course_enrolments', count(*) FROM academic.course_enrolments
UNION ALL SELECT 'academic.timetable_entries', count(*) FROM academic.timetable_entries
UNION ALL SELECT 'attendance_session.sessions', count(*) FROM attendance_session.sessions
UNION ALL SELECT 'attendance_session.session_students', count(*) FROM attendance_session.session_students
ORDER BY table_name;

SELECT
  s.id AS test_attendance_session_id,
  s.session_title,
  s.status,
  s.scheduled_start_at,
  s.scheduled_end_at,
  c.course_code,
  c.course_name
FROM attendance_session.sessions s
JOIN academic.course_offerings co ON co.id = s.course_offering_id
JOIN academic.courses c ON c.id = co.course_id
WHERE s.id = '40000000-0000-0000-0000-000000000001';
