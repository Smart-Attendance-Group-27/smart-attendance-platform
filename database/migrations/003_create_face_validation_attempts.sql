CREATE SCHEMA IF NOT EXISTS face_verification;

CREATE TABLE IF NOT EXISTS face_verification.face_validation_attempts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),

    verification_attempt_id uuid NOT NULL,

    face_profile_id uuid NOT NULL,

    attempt_number smallint NOT NULL,

    liveness_passed boolean,

    quality_passed boolean,

    similarity_score numeric(8, 7),

    verification_config_id uuid NOT NULL,

    validation_status character varying(20)
        NOT NULL
        DEFAULT 'pending',

    failure_reason character varying(100),

    captured_at timestamp with time zone
        NOT NULL
        DEFAULT now(),

    validated_at timestamp with time zone,

    CONSTRAINT fk_face_attempts_verification_attempt
        FOREIGN KEY (verification_attempt_id)
        REFERENCES attendance_verification.verification_attempts(id)
        ON DELETE RESTRICT,

    CONSTRAINT fk_face_attempts_face_profile
        FOREIGN KEY (face_profile_id)
        REFERENCES face_verification.face_profiles(id)
        ON DELETE RESTRICT,

    CONSTRAINT fk_face_attempts_verification_config
        FOREIGN KEY (verification_config_id)
        REFERENCES face_verification.verification_configs(id)
        ON DELETE RESTRICT,

    CONSTRAINT uq_face_attempts_verification_number
        UNIQUE (verification_attempt_id, attempt_number),

    CONSTRAINT chk_face_attempt_number_positive
        CHECK (attempt_number > 0),

    CONSTRAINT chk_face_similarity_score_range
        CHECK (
            similarity_score IS NULL
            OR similarity_score BETWEEN -1 AND 1
        ),

    CONSTRAINT chk_face_validation_status
        CHECK (
            validation_status IN (
                'pending',
                'passed',
                'failed'
            )
        ),

    CONSTRAINT chk_passed_face_attempt
        CHECK (
            validation_status <> 'passed'
            OR (
                liveness_passed = true
                AND quality_passed = true
                AND similarity_score IS NOT NULL
                AND validated_at IS NOT NULL
            )
        ),

    CONSTRAINT chk_failed_face_attempt
        CHECK (
            validation_status <> 'failed'
            OR (
                failure_reason IS NOT NULL
                AND validated_at IS NOT NULL
            )
        )
);

CREATE INDEX IF NOT EXISTS idx_face_attempts_profile
    ON face_verification.face_validation_attempts (face_profile_id);

CREATE INDEX IF NOT EXISTS idx_face_attempts_config
    ON face_verification.face_validation_attempts (verification_config_id);

CREATE INDEX IF NOT EXISTS idx_face_attempts_status
    ON face_verification.face_validation_attempts (validation_status);

ALTER TABLE face_verification.face_validation_attempts
    ENABLE ROW LEVEL SECURITY;