ALTER TABLE face_verification.face_profiles
    ADD COLUMN readiness_status character varying(20)
        NOT NULL
        DEFAULT 'not_checked',

    ADD COLUMN readiness_checked_at timestamp with time zone,

    ADD COLUMN readiness_config_id uuid,

    ADD CONSTRAINT fk_face_profiles_readiness_config
        FOREIGN KEY (readiness_config_id)
        REFERENCES face_verification.verification_configs(id)
        ON DELETE RESTRICT,

    ADD CONSTRAINT chk_face_profiles_readiness_status
        CHECK (
            readiness_status IN (
                'not_checked',
                'passed',
                'failed',
                'expired'
            )
        ),

    ADD CONSTRAINT chk_passed_readiness_has_details
        CHECK (
            readiness_status <> 'passed'
            OR (
                readiness_checked_at IS NOT NULL
                AND readiness_config_id IS NOT NULL
            )
        );