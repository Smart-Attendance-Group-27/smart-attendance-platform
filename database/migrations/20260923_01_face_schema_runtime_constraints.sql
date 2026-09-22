-- Reconcile the original baseline face tables with the runtime shape declared
-- by migrations 001-003. Those migrations use CREATE TABLE IF NOT EXISTS, so
-- a database created from smart_attendance_db_clean.sql retained the baseline
-- tables without the defaults, NOT NULL rules, and CHECK constraints.

BEGIN;

-- Fail before changing the schema when legacy rows cannot satisfy the runtime
-- model. An operator can repair the named data and safely re-run this file.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM face_verification.face_profiles
        WHERE student_id IS NULL
           OR embedding_generation_status IS NULL
           OR created_at IS NULL
           OR updated_at IS NULL
    ) THEN
        RAISE EXCEPTION 'face_profiles contains null values in runtime-required columns';
    END IF;

    IF EXISTS (
        SELECT 1 FROM face_verification.verification_configs
        WHERE similarity_threshold IS NULL
           OR is_active IS NULL
           OR configured_by IS NULL
           OR effective_from IS NULL
           OR created_at IS NULL
    ) THEN
        RAISE EXCEPTION 'verification_configs contains null values in runtime-required columns';
    END IF;

    IF EXISTS (
        SELECT 1 FROM face_verification.face_validation_attempts
        WHERE verification_attempt_id IS NULL
           OR face_profile_id IS NULL
           OR attempt_number IS NULL
           OR verification_config_id IS NULL
           OR validation_status IS NULL
           OR captured_at IS NULL
    ) THEN
        RAISE EXCEPTION 'face_validation_attempts contains null values in runtime-required columns';
    END IF;
END
$$;

ALTER TABLE face_verification.face_profiles
    ALTER COLUMN id SET DEFAULT gen_random_uuid(),
    ALTER COLUMN student_id SET NOT NULL,
    ALTER COLUMN embedding_generation_status SET DEFAULT 'pending',
    ALTER COLUMN embedding_generation_status SET NOT NULL,
    ALTER COLUMN created_at SET DEFAULT now(),
    ALTER COLUMN created_at SET NOT NULL,
    ALTER COLUMN updated_at SET DEFAULT now(),
    ALTER COLUMN updated_at SET NOT NULL;

ALTER TABLE face_verification.verification_configs
    ALTER COLUMN id SET DEFAULT gen_random_uuid(),
    ALTER COLUMN similarity_threshold SET NOT NULL,
    ALTER COLUMN is_active SET DEFAULT false,
    ALTER COLUMN is_active SET NOT NULL,
    ALTER COLUMN configured_by SET NOT NULL,
    ALTER COLUMN effective_from SET DEFAULT now(),
    ALTER COLUMN effective_from SET NOT NULL,
    ALTER COLUMN created_at SET DEFAULT now(),
    ALTER COLUMN created_at SET NOT NULL;

ALTER TABLE face_verification.face_validation_attempts
    ALTER COLUMN id SET DEFAULT gen_random_uuid(),
    ALTER COLUMN verification_attempt_id SET NOT NULL,
    ALTER COLUMN face_profile_id SET NOT NULL,
    ALTER COLUMN attempt_number SET NOT NULL,
    ALTER COLUMN verification_config_id SET NOT NULL,
    ALTER COLUMN validation_status SET DEFAULT 'pending',
    ALTER COLUMN validation_status SET NOT NULL,
    ALTER COLUMN captured_at SET DEFAULT now(),
    ALTER COLUMN captured_at SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'face_verification.face_profiles'::regclass
          AND conname = 'chk_face_profile_generation_status'
    ) THEN
        ALTER TABLE face_verification.face_profiles
            ADD CONSTRAINT chk_face_profile_generation_status
            CHECK (embedding_generation_status IN ('pending', 'generated', 'failed', 'revoked'));
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'face_verification.verification_configs'::regclass
          AND conname = 'chk_similarity_threshold_range'
    ) THEN
        ALTER TABLE face_verification.verification_configs
            ADD CONSTRAINT chk_similarity_threshold_range
            CHECK (similarity_threshold >= 0 AND similarity_threshold <= 1);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'face_verification.face_validation_attempts'::regclass
          AND conname = 'chk_face_attempt_number_positive'
    ) THEN
        ALTER TABLE face_verification.face_validation_attempts
            ADD CONSTRAINT chk_face_attempt_number_positive
            CHECK (attempt_number > 0);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'face_verification.face_validation_attempts'::regclass
          AND conname = 'chk_face_similarity_score_range'
    ) THEN
        ALTER TABLE face_verification.face_validation_attempts
            ADD CONSTRAINT chk_face_similarity_score_range
            CHECK (similarity_score IS NULL OR similarity_score BETWEEN -1 AND 1);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'face_verification.face_validation_attempts'::regclass
          AND conname = 'chk_face_validation_status'
    ) THEN
        ALTER TABLE face_verification.face_validation_attempts
            ADD CONSTRAINT chk_face_validation_status
            CHECK (validation_status IN ('pending', 'passed', 'failed'));
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'face_verification.face_validation_attempts'::regclass
          AND conname = 'chk_passed_face_attempt'
    ) THEN
        ALTER TABLE face_verification.face_validation_attempts
            ADD CONSTRAINT chk_passed_face_attempt
            CHECK (
                validation_status <> 'passed'
                OR (
                    liveness_passed = true
                    AND quality_passed = true
                    AND similarity_score IS NOT NULL
                    AND validated_at IS NOT NULL
                )
            );
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'face_verification.face_validation_attempts'::regclass
          AND conname = 'chk_failed_face_attempt'
    ) THEN
        ALTER TABLE face_verification.face_validation_attempts
            ADD CONSTRAINT chk_failed_face_attempt
            CHECK (
                validation_status <> 'failed'
                OR (failure_reason IS NOT NULL AND validated_at IS NOT NULL)
            );
    END IF;
END
$$;

COMMIT;
