\set ON_ERROR_STOP on

BEGIN;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM attendance_session.sessions
    WHERE id = '40000000-0000-0000-0000-000000000001'
  ) THEN
    RAISE EXCEPTION 'Canonical development session is missing';
  END IF;
END
$$;

-- Session A is the near-centre case. Refresh its window whenever this overlay
-- is applied so a newly initialized local database is immediately usable.
UPDATE attendance_session.sessions
SET session_title = 'Geofence Demo - Near Centre',
    scheduled_start_at = now() - INTERVAL '5 minutes',
    scheduled_end_at = now() + INTERVAL '7 days',
    check_in_opens_at = now() - INTERVAL '2 minutes',
    check_in_closes_at = now() + INTERVAL '7 days',
    late_after_at = now() + INTERVAL '15 minutes',
    status = 'active',
    requires_face_verification = true,
    requires_geofence = true,
    requires_qr = false,
    activated_at = now() - INTERVAL '2 minutes',
    closed_at = NULL,
    cancelled_at = NULL,
    cancellation_reason = NULL,
    updated_at = now()
WHERE id = '40000000-0000-0000-0000-000000000001';

UPDATE attendance_session.session_geofences
SET centre_latitude = 6.795132,
    centre_longitude = 79.900421,
    radius_m = 60,
    accuracy_buffer_m = 10,
    maximum_allowed_accuracy_m = 50,
    updated_at = now()
WHERE session_id = '40000000-0000-0000-0000-000000000001';

-- Session B uses the same real course and timetable relationships. Its centre
-- is roughly 2.2 km north of Session A for a deterministic outside case.
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
  '40000000-0000-0000-0000-000000000002',
  '37000000-0000-0000-0000-000000000001',
  '3a000000-0000-0000-0000-000000000001',
  NULL,
  '20000000-0000-0000-0000-000000000002',
  'Geofence Demo - Far Centre',
  'lecture',
  now() - INTERVAL '5 minutes',
  now() + INTERVAL '7 days',
  now() - INTERVAL '2 minutes',
  now() + INTERVAL '7 days',
  now() + INTERVAL '15 minutes',
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
  session_id, centre_latitude, centre_longitude, radius_m,
  accuracy_buffer_m, maximum_allowed_accuracy_m, created_at, updated_at
)
VALUES (
  '40000000-0000-0000-0000-000000000002',
  6.815132,
  79.900421,
  60,
  10,
  50,
  now(),
  now()
)
ON CONFLICT (session_id) DO UPDATE SET
  centre_latitude = EXCLUDED.centre_latitude,
  centre_longitude = EXCLUDED.centre_longitude,
  radius_m = EXCLUDED.radius_m,
  accuracy_buffer_m = EXCLUDED.accuracy_buffer_m,
  maximum_allowed_accuracy_m = EXCLUDED.maximum_allowed_accuracy_m,
  updated_at = now();

INSERT INTO attendance_session.session_students (
  id, session_id, student_id, course_enrolment_id, created_at
)
VALUES
  ('41000000-0000-0000-0000-000000000011', '40000000-0000-0000-0000-000000000002', '23000000-0000-0000-0000-000000000001', '39000000-0000-0000-0000-000000000001', now()),
  ('41000000-0000-0000-0000-000000000012', '40000000-0000-0000-0000-000000000002', '23000000-0000-0000-0000-000000000002', '39000000-0000-0000-0000-000000000002', now()),
  ('41000000-0000-0000-0000-000000000013', '40000000-0000-0000-0000-000000000002', '23000000-0000-0000-0000-000000000003', '39000000-0000-0000-0000-000000000003', now()),
  ('41000000-0000-0000-0000-000000000014', '40000000-0000-0000-0000-000000000002', '23000000-0000-0000-0000-000000000004', '39000000-0000-0000-0000-000000000004', now()),
  ('41000000-0000-0000-0000-000000000015', '40000000-0000-0000-0000-000000000002', '23000000-0000-0000-0000-000000000005', '39000000-0000-0000-0000-000000000005', now()),
  ('41000000-0000-0000-0000-000000000016', '40000000-0000-0000-0000-000000000002', '23000000-0000-0000-0000-000000000006', '39000000-0000-0000-0000-000000000006', now())
ON CONFLICT (session_id, student_id) DO UPDATE SET
  course_enrolment_id = EXCLUDED.course_enrolment_id;

COMMIT;
