BEGIN;

CREATE TABLE IF NOT EXISTS academic.correction_requests (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    requested_by uuid NOT NULL REFERENCES identity.users(id) ON DELETE RESTRICT,
    request_type varchar(20) NOT NULL,
    course_offering_id uuid NOT NULL REFERENCES academic.course_offerings(id) ON DELETE RESTRICT,
    timetable_entry_id uuid NULL REFERENCES academic.timetable_entries(id) ON DELETE RESTRICT,
    category varchar(40) NOT NULL,
    description text NOT NULL,
    status varchar(20) NOT NULL DEFAULT 'pending',
    reviewed_by uuid NULL REFERENCES identity.users(id) ON DELETE RESTRICT,
    reviewed_at timestamptz NULL,
    review_note text NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_correction_requests_type
        CHECK (request_type IN ('course_data', 'timetable')),
    CONSTRAINT ck_correction_requests_status
        CHECK (status IN ('pending', 'approved', 'rejected', 'resolved')),
    CONSTRAINT ck_correction_requests_description
        CHECK (char_length(description) BETWEEN 10 AND 1000),
    CONSTRAINT ck_correction_requests_timetable_entry
        CHECK (request_type <> 'timetable' OR timetable_entry_id IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_correction_requests_requester
    ON academic.correction_requests (requested_by, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_correction_requests_pending
    ON academic.correction_requests (created_at) WHERE status = 'pending';

COMMIT;
