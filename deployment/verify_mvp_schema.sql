-- Run with psql -v ON_ERROR_STOP=1 after applying the target migrations.
-- This script is read-only and prints no credentials or application data.

DO $$
DECLARE
    missing_columns text;
    missing_relations text;
    invalid_runtime_columns text;
    missing_constraints text;
BEGIN
    SELECT string_agg(format('%I.%I.%I', required.schema_name, required.table_name, required.column_name), ', ')
    INTO missing_columns
    FROM (VALUES
        ('identity', 'users', 'keycloak_user_id'),
        ('attendance_session', 'sessions', 'check_in_opens_at_explicit'),
        ('attendance_session', 'sessions', 'check_in_closes_at_explicit'),
        ('attendance_session', 'sessions', 'late_after_at_explicit'),
        ('attendance_session', 'session_geofences', 'centre_latitude'),
        ('attendance_session', 'session_geofences', 'centre_longitude'),
        ('attendance_session', 'session_geofences', 'radius_m'),
        ('attendance_session', 'qr_token_batches', 'voided_at'),
        ('attendance_session', 'qr_token_batches', 'voided_by'),
        ('attendance_session', 'qr_token_batches', 'void_reason'),
        ('attendance_verification', 'verification_attempts', 'checked_in_at'),
        ('attendance_verification', 'verification_attempts', 'initial_check_in_status'),
        ('attendance_verification', 'qr_validation_attempts', 'qr_batch_id'),
        ('face_verification', 'face_profiles', 'embedding_encrypted'),
        ('face_verification', 'face_profiles', 'embedding_model_name'),
        ('face_verification', 'face_profiles', 'embedding_model_version'),
        ('face_verification', 'face_profiles', 'embedding_dimension'),
        ('face_verification', 'face_profiles', 'readiness_status'),
        ('face_verification', 'face_validation_attempts', 'liveness_passed'),
        ('notification', 'delivery_attempts', 'next_attempt_at')
    ) AS required(schema_name, table_name, column_name)
    WHERE NOT EXISTS (
        SELECT 1
        FROM information_schema.columns AS existing
        WHERE existing.table_schema = required.schema_name
          AND existing.table_name = required.table_name
          AND existing.column_name = required.column_name
    );

    IF missing_columns IS NOT NULL THEN
        RAISE EXCEPTION 'MVP schema is missing required columns: %', missing_columns;
    END IF;

    SELECT string_agg(required.relation_name, ', ')
    INTO missing_relations
    FROM (VALUES
        ('academic.attendance_policies'),
        ('face_verification.face_profiles'),
        ('face_verification.verification_configs'),
        ('face_verification.face_validation_attempts'),
        ('face_verification.uq_face_profiles_student_id'),
        ('face_verification.idx_face_profiles_generation_status'),
        ('face_verification.uq_verification_configs_one_active'),
        ('face_verification.uq_face_attempts_verification_number'),
        ('face_verification.idx_face_attempts_profile'),
        ('face_verification.idx_face_attempts_config'),
        ('face_verification.idx_face_attempts_status'),
        ('notification.notifications'),
        ('notification.device_tokens'),
        ('notification.delivery_attempts'),
        ('notification.idx_device_tokens_active_user_android'),
        ('notification.idx_notifications_recipient_visible'),
        ('notification.idx_delivery_attempts_status_queued'),
        ('notification.idx_delivery_attempts_notification_id'),
        ('notification.idx_delivery_attempts_ready'),
        ('notification.uq_notifications_upcoming_class_session_user')
    ) AS required(relation_name)
    WHERE to_regclass(required.relation_name) IS NULL;

    IF missing_relations IS NOT NULL THEN
        RAISE EXCEPTION 'MVP schema is missing required tables or indexes: %', missing_relations;
    END IF;

    SELECT string_agg(format('%I.%I.%I', required.schema_name, required.table_name, required.column_name), ', ')
    INTO invalid_runtime_columns
    FROM (VALUES
        ('face_verification', 'face_profiles', 'id', true),
        ('face_verification', 'face_profiles', 'student_id', false),
        ('face_verification', 'face_profiles', 'embedding_generation_status', true),
        ('face_verification', 'face_profiles', 'created_at', true),
        ('face_verification', 'face_profiles', 'updated_at', true),
        ('face_verification', 'face_profiles', 'readiness_status', true),
        ('face_verification', 'verification_configs', 'id', true),
        ('face_verification', 'verification_configs', 'similarity_threshold', false),
        ('face_verification', 'verification_configs', 'is_active', true),
        ('face_verification', 'verification_configs', 'configured_by', false),
        ('face_verification', 'verification_configs', 'effective_from', true),
        ('face_verification', 'verification_configs', 'created_at', true),
        ('face_verification', 'face_validation_attempts', 'id', true),
        ('face_verification', 'face_validation_attempts', 'verification_attempt_id', false),
        ('face_verification', 'face_validation_attempts', 'face_profile_id', false),
        ('face_verification', 'face_validation_attempts', 'attempt_number', false),
        ('face_verification', 'face_validation_attempts', 'verification_config_id', false),
        ('face_verification', 'face_validation_attempts', 'validation_status', true),
        ('face_verification', 'face_validation_attempts', 'captured_at', true)
    ) AS required(schema_name, table_name, column_name, requires_default)
    JOIN information_schema.columns AS existing
      ON existing.table_schema = required.schema_name
     AND existing.table_name = required.table_name
     AND existing.column_name = required.column_name
    WHERE existing.is_nullable <> 'NO'
       OR (required.requires_default AND existing.column_default IS NULL);

    IF invalid_runtime_columns IS NOT NULL THEN
        RAISE EXCEPTION 'Face runtime columns are nullable or missing defaults: %', invalid_runtime_columns;
    END IF;

    SELECT string_agg(required.constraint_name, ', ')
    INTO missing_constraints
    FROM (VALUES
        ('face_verification.face_profiles', 'chk_face_profile_generation_status'),
        ('face_verification.face_profiles', 'chk_generated_profile_has_encrypted_embedding'),
        ('face_verification.face_profiles', 'chk_face_profiles_readiness_status'),
        ('face_verification.face_profiles', 'chk_passed_readiness_has_details'),
        ('face_verification.face_profiles', 'chk_face_profiles_embedding_dimension'),
        ('face_verification.verification_configs', 'chk_similarity_threshold_range'),
        ('face_verification.face_validation_attempts', 'chk_face_attempt_number_positive'),
        ('face_verification.face_validation_attempts', 'chk_face_similarity_score_range'),
        ('face_verification.face_validation_attempts', 'chk_face_validation_status'),
        ('face_verification.face_validation_attempts', 'chk_passed_face_attempt'),
        ('face_verification.face_validation_attempts', 'chk_failed_face_attempt')
    ) AS required(table_name, constraint_name)
    WHERE NOT EXISTS (
        SELECT 1 FROM pg_constraint AS existing
        WHERE existing.conrelid = required.table_name::regclass
          AND existing.conname = required.constraint_name
    );

    IF missing_constraints IS NOT NULL THEN
        RAISE EXCEPTION 'Face runtime constraints are missing: %', missing_constraints;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'face_verification'
          AND table_name = 'face_profiles'
          AND column_name = 'embedding'
    ) THEN
        RAISE EXCEPTION 'Plaintext face_profiles.embedding still exists; complete migrations 005 and 006';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM notification.notification_types
        WHERE code = 'ATTENDANCE_SESSION_CANCELLED'
          AND is_active IS TRUE
    ) THEN
        RAISE EXCEPTION 'ATTENDANCE_SESSION_CANCELLED notification type is missing or inactive';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM academic.attendance_policies WHERE is_active IS TRUE
    ) THEN
        RAISE EXCEPTION 'No active attendance policy exists';
    END IF;
END
$$;

SELECT
    EXISTS (
        SELECT 1 FROM face_verification.verification_configs WHERE is_active IS TRUE
    ) AS face_readiness_has_active_threshold,
    COUNT(*) FILTER (
        WHERE embedding_generation_status = 'generated'
    ) AS generated_reference_faces
FROM face_verification.face_profiles;
