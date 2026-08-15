CREATE SCHEMA IF NOT EXISTS face_verification;

CREATE TABLE IF NOT EXISTS face_verification.face_profiles (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),

    student_id uuid NOT NULL,

    embedding double precision[],

    embedding_generation_status character varying(20)
        NOT NULL
        DEFAULT 'pending',

    generated_at timestamp with time zone,

    created_at timestamp with time zone
        NOT NULL
        DEFAULT now(),

    updated_at timestamp with time zone
        NOT NULL
        DEFAULT now(),

    CONSTRAINT fk_face_profiles_student
        FOREIGN KEY (student_id)
        REFERENCES academic.student_profiles(id)
        ON DELETE RESTRICT,

    CONSTRAINT uq_face_profiles_student_id
        UNIQUE (student_id),

    CONSTRAINT chk_face_profile_generation_status
        CHECK (
            embedding_generation_status IN (
                'pending',
                'generated',
                'failed',
                'revoked'
            )
        ),

    CONSTRAINT chk_generated_profile_has_embedding
        CHECK (
            embedding_generation_status <> 'generated'
            OR (
                embedding IS NOT NULL
                AND array_length(embedding, 1) > 0
                AND generated_at IS NOT NULL
            )
        )
);

CREATE INDEX IF NOT EXISTS idx_face_profiles_generation_status
    ON face_verification.face_profiles (
        embedding_generation_status
    );
