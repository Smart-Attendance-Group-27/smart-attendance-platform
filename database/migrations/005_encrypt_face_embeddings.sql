ALTER TABLE face_verification.face_profiles
    ADD COLUMN embedding_encrypted bytea,
    ADD COLUMN embedding_model_name character varying(100),
    ADD COLUMN embedding_model_version character varying(50),
    ADD COLUMN embedding_dimension integer;

ALTER TABLE face_verification.face_profiles
    DROP CONSTRAINT IF EXISTS chk_generated_profile_has_embedding;

ALTER TABLE face_verification.face_profiles
    ADD CONSTRAINT chk_face_profiles_embedding_dimension
        CHECK (embedding_dimension IS NULL OR embedding_dimension > 0),

    ADD CONSTRAINT chk_generated_profile_has_encrypted_embedding
        CHECK (
            embedding_generation_status <> 'generated'
            OR (
                embedding_encrypted IS NOT NULL
                AND octet_length(embedding_encrypted) > 0
                AND embedding_model_name IS NOT NULL
                AND length(trim(embedding_model_name)) > 0
                AND embedding_model_version IS NOT NULL
                AND length(trim(embedding_model_version)) > 0
                AND embedding_dimension IS NOT NULL
                AND embedding_dimension > 0
                AND generated_at IS NOT NULL
            )
        );