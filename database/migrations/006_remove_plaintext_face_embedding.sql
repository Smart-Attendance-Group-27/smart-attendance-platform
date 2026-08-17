DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM face_verification.face_profiles
        WHERE embedding IS NOT NULL
    ) THEN
        RAISE EXCEPTION
            'Cannot remove embedding column: plaintext values still exist';
    END IF;
END
$$;

ALTER TABLE face_verification.face_profiles
    DROP COLUMN embedding;