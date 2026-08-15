CREATE SCHEMA IF NOT EXISTS face_verification;

CREATE TABLE IF NOT EXISTS face_verification.verification_configs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),

    similarity_threshold numeric(6, 5)
        NOT NULL,

    is_active boolean
        NOT NULL
        DEFAULT false,

    configured_by uuid NOT NULL,

    effective_from timestamp with time zone
        NOT NULL
        DEFAULT now(),

    created_at timestamp with time zone
        NOT NULL
        DEFAULT now(),

    CONSTRAINT fk_verification_configs_configured_by
        FOREIGN KEY (configured_by)
        REFERENCES identity.users(id)
        ON DELETE RESTRICT,

    CONSTRAINT chk_similarity_threshold_range
        CHECK (
            similarity_threshold >= 0
            AND similarity_threshold <= 1
        )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_verification_configs_one_active
    ON face_verification.verification_configs (is_active)
    WHERE is_active = true;