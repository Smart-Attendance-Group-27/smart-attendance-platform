BEGIN;

CREATE TABLE IF NOT EXISTS academic.attendance_policies (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    check_in_window_minutes smallint NOT NULL,
    late_threshold_minutes smallint NOT NULL,
    qr_default_validity_minutes smallint NOT NULL,
    is_active boolean NOT NULL DEFAULT false,
    configured_by uuid NULL REFERENCES identity.users(id) ON DELETE RESTRICT,
    effective_from timestamptz NOT NULL DEFAULT now(),
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_attendance_policies_window
        CHECK (check_in_window_minutes BETWEEN 1 AND 180),
    CONSTRAINT ck_attendance_policies_late
        CHECK (late_threshold_minutes BETWEEN 0 AND check_in_window_minutes),
    CONSTRAINT ck_attendance_policies_qr_validity
        CHECK (qr_default_validity_minutes BETWEEN 1 AND 60)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_attendance_policies_one_active
    ON academic.attendance_policies (is_active) WHERE is_active;

INSERT INTO academic.attendance_policies (
    check_in_window_minutes, late_threshold_minutes,
    qr_default_validity_minutes, is_active
)
SELECT 15, 10, 5, true
WHERE NOT EXISTS (
    SELECT 1 FROM academic.attendance_policies WHERE is_active
);

COMMIT;
