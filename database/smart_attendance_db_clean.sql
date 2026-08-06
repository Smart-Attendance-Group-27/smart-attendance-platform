

BEGIN;

CREATE SCHEMA IF NOT EXISTS identity;
CREATE SCHEMA IF NOT EXISTS academic;
CREATE SCHEMA IF NOT EXISTS attendance_session;
CREATE SCHEMA IF NOT EXISTS attendance_verification;
CREATE SCHEMA IF NOT EXISTS face_verification;
CREATE SCHEMA IF NOT EXISTS notification;
CREATE SCHEMA IF NOT EXISTS reporting;
CREATE SCHEMA IF NOT EXISTS audit;

CREATE TABLE identity.users (
  "id" uuid,
  "email" character varying(255),
  "password_hash" character varying(255),
  "account_status" character varying(20),
  "failed_login_attempts" smallint,
  "locked_until" timestamp with time zone,
  "last_login_at" timestamp with time zone,
  "must_change_password" boolean,
  "password_changed_at" timestamp with time zone,
  "created_by" uuid,
  "created_at" timestamp with time zone,
  "updated_at" timestamp with time zone,
  PRIMARY KEY ("id"),
  CONSTRAINT "FK_users_created_by"
    FOREIGN KEY ("created_by")
      REFERENCES identity.users("id")
);

CREATE UNIQUE INDEX uq_users_email ON identity.users ("email");

CREATE TABLE academic.faculties (
  "id" uuid,
  "university_faculty_id" uuid,
  "faculty_name" character varying(150),
  "status" character varying(20),
  "last_synced_at" timestamp with time zone,
  "created_at" timestamp with time zone,
  "updated_at" timestamp with time zone,
  PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX uq_faculties_university_faculty_id ON academic.faculties ("university_faculty_id");

CREATE TABLE academic.departments (
  "id" uuid,
  "university_department_id" uuid,
  "faculty_id" uuid,
  "department_name" character varying(150),
  "status" character varying(20),
  "last_synced_at" timestamp with time zone,
  "created_at" timestamp with time zone,
  "updated_at" timestamp with time zone,
  PRIMARY KEY ("id"),
  CONSTRAINT "FK_departments_faculty_id"
    FOREIGN KEY ("faculty_id")
      REFERENCES academic.faculties("id")
);

CREATE UNIQUE INDEX uq_departments_university_department_id ON academic.departments ("university_department_id");

CREATE TABLE academic.student_profiles (
  "id" uuid,
  "user_id" uuid NOT NULL,
  "registration_number" character varying(30),
  "first_name" character varying(100),
  "middle_name" character varying(100),
  "last_name" character varying(100),
  "department_id" uuid,
  "intake_year" smallint,
  "current_semester" smallint,
  "profile_status" character varying(20),
  "last_synced_at" timestamp with time zone,
  "created_at" timestamp with time zone,
  "updated_at" timestamp with time zone,
  PRIMARY KEY ("id"),
  CONSTRAINT "FK_student_profiles_user_id"
    FOREIGN KEY ("user_id")
      REFERENCES identity.users("id"),
  CONSTRAINT "FK_student_profiles_department_id"
    FOREIGN KEY ("department_id")
      REFERENCES academic.departments("id")
);

CREATE UNIQUE INDEX uq_student_profiles_user_id ON academic.student_profiles ("user_id");
CREATE UNIQUE INDEX uq_student_profiles_registration_number ON academic.student_profiles ("registration_number");

CREATE TABLE academic.buildings (
  "id" uuid,
  "building_name" character varying(150),
  "status" character varying(20),
  "created_at" timestamp with time zone,
  "updated_at" timestamp with time zone,
  PRIMARY KEY ("id")
);

CREATE TABLE academic.classrooms (
  "id" uuid,
  "building_id" uuid,
  "classroom_code" character varying(30),
  "floor_number" smallint,
  "capacity" integer,
  "latitude" numeric,
  "longitude" numeric,
  "default_geofence_radius_m" numeric,
  "status" character varying(20),
  "created_at" timestamp with time zone,
  "updated_at" timestamp with time zone,
  PRIMARY KEY ("id"),
  CONSTRAINT "FK_classrooms_building_id"
    FOREIGN KEY ("building_id")
      REFERENCES academic.buildings("id")
);

CREATE UNIQUE INDEX uq_classrooms_building_code ON academic.classrooms ("building_id", "classroom_code");

CREATE TABLE academic.academic_years (
  "id" uuid,
  "lms_academic_year_id" uuid,
  "start_date" date,
  "end_date" date,
  "status" character varying(20),
  "last_synced_at" timestamp with time zone,
  "created_at" timestamp with time zone,
  "updated_at" timestamp with time zone,
  PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX uq_academic_years_lms_id ON academic.academic_years ("lms_academic_year_id");

CREATE TABLE academic.semesters (
  "id" uuid,
  "lms_semester_id" uuid,
  "academic_year_id" uuid,
  "semester_number" smallint,
  "start_date" date,
  "end_date" date,
  "status" character varying(20),
  "last_synced_at" timestamp with time zone,
  "created_at" timestamp with time zone,
  "updated_at" timestamp with time zone,
  PRIMARY KEY ("id"),
  CONSTRAINT "FK_semesters_academic_year_id"
    FOREIGN KEY ("academic_year_id")
      REFERENCES academic.academic_years("id")
);

CREATE UNIQUE INDEX uq_semesters_lms_id ON academic.semesters ("lms_semester_id");
CREATE UNIQUE INDEX uq_semesters_academic_year_number ON academic.semesters ("academic_year_id", "semester_number");

CREATE TABLE academic.courses (
  "id" uuid,
  "course_code" character varying(30),
  "course_name" character varying(255),
  "department_id" uuid,
  "credits" numeric,
  "course_description" text,
  "status" character varying(20),
  "last_synced_at" timestamp with time zone,
  "created_at" timestamp with time zone,
  "updated_at" timestamp with time zone,
  PRIMARY KEY ("id"),
  CONSTRAINT "FK_courses_department_id"
    FOREIGN KEY ("department_id")
      REFERENCES academic.departments("id")
);

CREATE UNIQUE INDEX uq_courses_course_code ON academic.courses ("course_code");

CREATE TABLE academic.course_offerings (
  "id" uuid,
  "lms_course_offering_id" uuid,
  "course_id" uuid,
  "semester_id" uuid,
  "batch_year" smallint,
  "course_type" character varying(20),
  "attendance_threshold" numeric,
  "status" character varying(20),
  "last_synced_at" timestamp with time zone,
  "created_at" timestamp with time zone,
  "updated_at" timestamp with time zone,
  PRIMARY KEY ("id"),
  CONSTRAINT "FK_course_offerings_semester_id"
    FOREIGN KEY ("semester_id")
      REFERENCES academic.semesters("id"),
  CONSTRAINT "FK_course_offerings_course_id"
    FOREIGN KEY ("course_id")
      REFERENCES academic.courses("id")
);

CREATE UNIQUE INDEX uq_course_offerings_lms_id ON academic.course_offerings ("lms_course_offering_id");
CREATE UNIQUE INDEX uq_course_offerings_natural ON academic.course_offerings ("course_id", "semester_id", "batch_year", "course_type");

CREATE TABLE academic.timetable_entries (
  "id" uuid,
  "course_offering_id" uuid,
  "classroom_id" uuid,
  "day_of_week" smallint,
  "start_time" time without time zone,
  "end_time" time without time zone,
  "course_type" character varying(20),
  "valid_from" date,
  "valid_until" date,
  "status" character varying(20),
  "created_by" uuid,
  "created_at" timestamp with time zone,
  "updated_at" timestamp with time zone,
  PRIMARY KEY ("id"),
  CONSTRAINT "FK_timetable_entries_created_by"
    FOREIGN KEY ("created_by")
      REFERENCES identity.users("id"),
  CONSTRAINT "FK_timetable_entries_classroom_id"
    FOREIGN KEY ("classroom_id")
      REFERENCES academic.classrooms("id"),
  CONSTRAINT "FK_timetable_entries_course_offering_id"
    FOREIGN KEY ("course_offering_id")
      REFERENCES academic.course_offerings("id")
);

CREATE UNIQUE INDEX uq_timetable_entries_schedule ON academic.timetable_entries ("course_offering_id", "day_of_week", "start_time", "valid_from");

CREATE TABLE academic.timetable_exceptions (
  "id" uuid,
  "timetable_entry_id" uuid,
  "original_date" date,
  "exception_type" character varying(30),
  "new_date" date,
  "new_start_time" time without time zone,
  "new_end_time" time without time zone,
  "new_classroom_id" uuid,
  "reason" text,
  "created_by" uuid,
  "created_at" timestamp with time zone,
  PRIMARY KEY ("id"),
  CONSTRAINT "FK_timetable_exceptions_new_classroom_id"
    FOREIGN KEY ("new_classroom_id")
      REFERENCES academic.classrooms("id"),
  CONSTRAINT "FK_timetable_exceptions_timetable_entry_id"
    FOREIGN KEY ("timetable_entry_id")
      REFERENCES academic.timetable_entries("id"),
  CONSTRAINT "FK_timetable_exceptions_created_by"
    FOREIGN KEY ("created_by")
      REFERENCES identity.users("id")
);

CREATE UNIQUE INDEX uq_timetable_exceptions_entry_date ON academic.timetable_exceptions ("timetable_entry_id", "original_date");

CREATE TABLE attendance_session.sessions (
  "id" uuid,
  "course_offering_id" uuid,
  "timetable_entry_id" uuid,
  "timetable_exception_id" uuid,
  "created_by" uuid,
  "session_title" character varying(255),
  "session_type" character varying(20),
  "scheduled_start_at" timestamp with time zone,
  "scheduled_end_at" timestamp with time zone,
  "check_in_opens_at" timestamp with time zone,
  "check_in_closes_at" timestamp with time zone,
  "late_after_at" timestamp with time zone,
  "status" character varying(20),
  "requires_face_verification" boolean,
  "requires_geofence" boolean,
  "requires_qr" boolean,
  "activated_at" timestamp with time zone,
  "closed_at" timestamp with time zone,
  "cancelled_at" timestamp with time zone,
  "cancellation_reason" text,
  "created_at" timestamp with time zone,
  "updated_at" timestamp with time zone,
  PRIMARY KEY ("id"),
  CONSTRAINT "FK_sessions_timetable_entry_id"
    FOREIGN KEY ("timetable_entry_id")
      REFERENCES academic.timetable_entries("id"),
  CONSTRAINT "FK_sessions_created_by"
    FOREIGN KEY ("created_by")
      REFERENCES identity.users("id"),
  CONSTRAINT "FK_sessions_course_offering_id"
    FOREIGN KEY ("course_offering_id")
      REFERENCES academic.course_offerings("id"),
  CONSTRAINT "FK_sessions_timetable_exception_id"
    FOREIGN KEY ("timetable_exception_id")
      REFERENCES academic.timetable_exceptions("id")
);

CREATE TABLE attendance_verification.verification_attempts (
  "id" uuid,
  "session_id" uuid,
  "student_id" uuid,
  "status" character varying(20),
  "failure_reason" character varying(100),
  "started_at" timestamp with time zone,
  "completed_at" timestamp with time zone,
  PRIMARY KEY ("id"),
  CONSTRAINT "FK_verification_attempts_student_id"
    FOREIGN KEY ("student_id")
      REFERENCES academic.student_profiles("id"),
  CONSTRAINT "FK_verification_attempts_session_id"
    FOREIGN KEY ("session_id")
      REFERENCES attendance_session.sessions("id")
);

CREATE UNIQUE INDEX uq_verification_attempts_session_student ON attendance_verification.verification_attempts ("session_id", "student_id");

CREATE TABLE attendance_verification.manual_reviews (
  "verification_attempt_id" uuid,
  "review_status" character varying(20),
  "reviewed_by" uuid,
  "decision_reason" text,
  "reviewed_at" timestamp with time zone,
  PRIMARY KEY ("verification_attempt_id"),
  CONSTRAINT "FK_manual_reviews_reviewed_by"
    FOREIGN KEY ("reviewed_by")
      REFERENCES identity.users("id"),
  CONSTRAINT "FK_manual_reviews_verification_attempt_id"
    FOREIGN KEY ("verification_attempt_id")
      REFERENCES attendance_verification.verification_attempts("id")
);

CREATE TABLE identity.roles (
  "id" uuid,
  "role_code" character varying(50),
  "description" text,
  "created_at" timestamp with time zone,
  PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX uq_roles_role_code ON identity.roles ("role_code");

CREATE TABLE identity.user_roles (
  "user_id" uuid,
  "role_id" uuid,
  "assigned_by" uuid,
  "assigned_at" timestamp with time zone,
  "is_active" boolean,
  PRIMARY KEY ("user_id", "role_id"),
  CONSTRAINT "FK_user_roles_user_id"
    FOREIGN KEY ("user_id")
      REFERENCES identity.users("id"),
  CONSTRAINT "FK_user_roles_assigned_by"
    FOREIGN KEY ("assigned_by")
      REFERENCES identity.users("id"),
  CONSTRAINT "FK_user_roles_role_id"
    FOREIGN KEY ("role_id")
      REFERENCES identity.roles("id")
);

CREATE TABLE face_verification.verification_configs (
  "id" uuid,
  "similarity_threshold" numeric,
  "is_active" boolean,
  "configured_by" uuid,
  "effective_from" timestamp with time zone,
  "created_at" timestamp with time zone,
  PRIMARY KEY ("id"),
  CONSTRAINT "FK_verification_configs_configured_by"
    FOREIGN KEY ("configured_by")
      REFERENCES identity.users("id")
);

CREATE TABLE academic.course_enrolments (
  "id" uuid,
  "course_offering_id" uuid,
  "student_id" uuid,
  "enrolment_status" character varying(20),
  "enrolled_at" timestamp with time zone,
  "dropped_at" timestamp with time zone,
  "last_synced_at" timestamp with time zone,
  "created_at" timestamp with time zone,
  "updated_at" timestamp with time zone,
  PRIMARY KEY ("id"),
  CONSTRAINT "FK_course_enrolments_course_offering_id"
    FOREIGN KEY ("course_offering_id")
      REFERENCES academic.course_offerings("id"),
  CONSTRAINT "FK_course_enrolments_student_id"
    FOREIGN KEY ("student_id")
      REFERENCES academic.student_profiles("id")
);

CREATE UNIQUE INDEX uq_course_enrolments_offering_student ON academic.course_enrolments ("course_offering_id", "student_id");

CREATE TABLE attendance_verification.geofence_validation_attempts (
  "id" uuid,
  "verification_attempt_id" uuid,
  "attempt_number" smallint,
  "accuracy_m" numeric,
  "distance_from_centre_m" numeric,
  "validation_status" character varying(20),
  "failure_reason" character varying(100),
  "captured_at" timestamp with time zone,
  "validated_at" timestamp with time zone,
  PRIMARY KEY ("id"),
  CONSTRAINT "FK_geofence_validation_attempts_verification_attempt_id"
    FOREIGN KEY ("verification_attempt_id")
      REFERENCES attendance_verification.verification_attempts("id")
);

CREATE UNIQUE INDEX uq_geofence_attempts_verification_number ON attendance_verification.geofence_validation_attempts ("verification_attempt_id", "attempt_number");

CREATE TABLE attendance_session.qr_token_batches (
  "id" uuid,
  "session_id" uuid,
  "refresh_interval_seconds" smallint,
  "issued_by" uuid,
  "status" character varying(20),
  "activated_at" timestamp with time zone,
  "deactivated_at" timestamp with time zone,
  "created_at" timestamp with time zone,
  PRIMARY KEY ("id"),
  CONSTRAINT "FK_qr_token_batches_session_id"
    FOREIGN KEY ("session_id")
      REFERENCES attendance_session.sessions("id"),
  CONSTRAINT "FK_qr_token_batches_issued_by"
    FOREIGN KEY ("issued_by")
      REFERENCES identity.users("id")
);

CREATE TABLE attendance_session.qr_tokens (
  "id" uuid,
  "qr_batch_id" uuid,
  "token_hash" character varying(255),
  "sequence_number" integer,
  "valid_from" timestamp with time zone,
  "expires_at" timestamp with time zone,
  "revoked_at" timestamp with time zone,
  "created_at" timestamp with time zone,
  PRIMARY KEY ("id"),
  CONSTRAINT "FK_qr_tokens_qr_batch_id"
    FOREIGN KEY ("qr_batch_id")
      REFERENCES attendance_session.qr_token_batches("id")
);

CREATE UNIQUE INDEX uq_qr_tokens_token_hash ON attendance_session.qr_tokens ("token_hash");
CREATE UNIQUE INDEX uq_qr_tokens_batch_sequence ON attendance_session.qr_tokens ("qr_batch_id", "sequence_number");

CREATE TABLE attendance_verification.qr_validation_attempts (
  "id" uuid,
  "verification_attempt_id" uuid,
  "qr_token_id" uuid,
  "attempt_number" smallint,
  "validation_status" character varying(20),
  "failure_reason" character varying(100),
  "validated_at" timestamp with time zone,
  PRIMARY KEY ("id"),
  CONSTRAINT "FK_qr_validation_attempts_qr_token_id"
    FOREIGN KEY ("qr_token_id")
      REFERENCES attendance_session.qr_tokens("id"),
  CONSTRAINT "FK_qr_validation_attempts_verification_attempt_id"
    FOREIGN KEY ("verification_attempt_id")
      REFERENCES attendance_verification.verification_attempts("id")
);

CREATE UNIQUE INDEX uq_qr_attempts_verification_number ON attendance_verification.qr_validation_attempts ("verification_attempt_id", "attempt_number");

CREATE TABLE identity.permissions (
  "id" uuid,
  "permission_code" character varying(100),
  "description" text,
  "created_at" timestamp with time zone,
  PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX uq_permissions_permission_code ON identity.permissions ("permission_code");

CREATE TABLE face_verification.face_profiles (
  "id" uuid,
  "student_id" uuid,
  "embedding" double precision[],
  "embedding_generation_status" character varying(20),
  "failure_reason" character varying(100),
  "generated_at" timestamp with time zone,
  "created_at" timestamp with time zone,
  "updated_at" timestamp with time zone,
  PRIMARY KEY ("id"),
  CONSTRAINT "FK_face_profiles_student_id"
    FOREIGN KEY ("student_id")
      REFERENCES academic.student_profiles("id")
);

CREATE UNIQUE INDEX uq_face_profiles_student_id ON face_verification.face_profiles ("student_id");

CREATE TABLE face_verification.face_validation_attempts (
  "id" uuid,
  "verification_attempt_id" uuid,
  "face_profile_id" uuid,
  "attempt_number" smallint,
  "liveness_passed" boolean,
  "quality_passed" boolean,
  "similarity_score" numeric,
  "verification_config_id" uuid,
  "validation_status" character varying(20),
  "failure_reason" character varying(100),
  "captured_at" timestamp with time zone,
  "validated_at" timestamp with time zone,
  PRIMARY KEY ("id"),
  CONSTRAINT "FK_face_validation_attempts_verification_attempt_id"
    FOREIGN KEY ("verification_attempt_id")
      REFERENCES attendance_verification.verification_attempts("id"),
  CONSTRAINT "FK_face_validation_attempts_face_profile_id"
    FOREIGN KEY ("face_profile_id")
      REFERENCES face_verification.face_profiles("id"),
  CONSTRAINT "FK_face_validation_attempts_verification_config_id"
    FOREIGN KEY ("verification_config_id")
      REFERENCES face_verification.verification_configs("id")
);

CREATE UNIQUE INDEX uq_face_attempts_verification_number ON face_verification.face_validation_attempts ("verification_attempt_id", "attempt_number");

CREATE TABLE reporting.report_requests (
  "id" uuid,
  "requested_by" uuid,
  "report_name" character varying(255),
  "report_type" character varying(50),
  "output_format" character varying(10),
  "filters" jsonb,
  "status" character varying(20),
  "storage_path" text,
  "failure_reason" text,
  "requested_at" timestamp with time zone,
  "started_at" timestamp with time zone,
  "completed_at" timestamp with time zone,
  "expires_at" timestamp with time zone,
  PRIMARY KEY ("id"),
  CONSTRAINT "FK_report_requests_requested_by"
    FOREIGN KEY ("requested_by")
      REFERENCES identity.users("id")
);

CREATE TABLE audit.audit_logs (
  "id" uuid,
  "actor_user_id" uuid,
  "actor_type" character varying(20),
  "source_service" character varying(50),
  "action" character varying(100),
  "entity_type" character varying(50),
  "entity_id" uuid,
  "outcome" character varying(20),
  "failure_reason" text,
  "old_values" jsonb,
  "new_values" jsonb,
  "metadata" jsonb,
  "occurred_at" timestamp with time zone,
  PRIMARY KEY ("id"),
  CONSTRAINT "FK_audit_logs_actor_user_id"
    FOREIGN KEY ("actor_user_id")
      REFERENCES identity.users("id")
);

CREATE TABLE identity.password_reset_tokens (
  "id" uuid,
  "user_id" uuid,
  "token_hash" character varying(255),
  "expires_at" timestamp with time zone,
  "used_at" timestamp with time zone,
  "created_at" timestamp with time zone,
  PRIMARY KEY ("id"),
  CONSTRAINT "FK_password_reset_tokens_user_id"
    FOREIGN KEY ("user_id")
      REFERENCES identity.users("id")
);

CREATE UNIQUE INDEX uq_password_reset_tokens_hash ON identity.password_reset_tokens ("token_hash");

CREATE TABLE notification.device_tokens (
  "id" uuid,
  "user_id" uuid,
  "expo_push_token" text,
  "platform" character varying(20),
  "is_active" boolean,
  "registered_at" timestamp with time zone,
  "last_used_at" timestamp with time zone,
  "revoked_at" timestamp with time zone,
  PRIMARY KEY ("id"),
  CONSTRAINT "FK_device_tokens_user_id"
    FOREIGN KEY ("user_id")
      REFERENCES identity.users("id")
);

CREATE UNIQUE INDEX uq_device_tokens_expo_push_token ON notification.device_tokens ("expo_push_token");

CREATE TABLE notification.notification_types (
  "code" character varying(50),
  "description" character varying(255),
  "default_in_app_enabled" boolean,
  "default_push_enabled" boolean,
  "default_email_enabled" boolean,
  "user_configurable" boolean,
  "is_active" boolean,
  "created_at" timestamp with time zone,
  "updated_at" timestamp with time zone,
  PRIMARY KEY ("code")
);

CREATE TABLE notification.notifications (
  "id" uuid,
  "recipient_user_id" uuid,
  "notification_type" character varying(50),
  "title" character varying(255),
  "body" text,
  "priority" character varying(10),
  "related_entity_type" character varying(30),
  "related_entity_id" uuid,
  "in_app_visible" boolean,
  "scheduled_for" timestamp with time zone,
  "read_at" timestamp with time zone,
  "expires_at" timestamp with time zone,
  "created_at" timestamp with time zone,
  PRIMARY KEY ("id"),
  CONSTRAINT "FK_notifications_notification_type"
    FOREIGN KEY ("notification_type")
      REFERENCES notification.notification_types("code"),
  CONSTRAINT "FK_notifications_recipient_user_id"
    FOREIGN KEY ("recipient_user_id")
      REFERENCES identity.users("id")
);

CREATE TABLE notification.delivery_attempts (
  "id" uuid,
  "notification_id" uuid,
  "channel" character varying(20),
  "device_token_id" uuid,
  "recipient_email" character varying(255),
  "attempt_number" smallint,
  "delivery_status" character varying(20),
  "provider_message_id" character varying(255),
  "failure_reason" character varying(255),
  "queued_at" timestamp with time zone,
  "attempted_at" timestamp with time zone,
  "completed_at" timestamp with time zone,
  PRIMARY KEY ("id"),
  CONSTRAINT "FK_delivery_attempts_device_token_id"
    FOREIGN KEY ("device_token_id")
      REFERENCES notification.device_tokens("id"),
  CONSTRAINT "FK_delivery_attempts_notification_id"
    FOREIGN KEY ("notification_id")
      REFERENCES notification.notifications("id")
);

CREATE TABLE attendance_session.session_students (
  "id" uuid,
  "session_id" uuid,
  "student_id" uuid,
  "course_enrolment_id" uuid,
  "created_at" timestamp with time zone,
  PRIMARY KEY ("id"),
  CONSTRAINT "FK_session_students_session_id"
    FOREIGN KEY ("session_id")
      REFERENCES attendance_session.sessions("id"),
  CONSTRAINT "FK_session_students_course_enrolment_id"
    FOREIGN KEY ("course_enrolment_id")
      REFERENCES academic.course_enrolments("id"),
  CONSTRAINT "FK_session_students_student_id"
    FOREIGN KEY ("student_id")
      REFERENCES academic.student_profiles("id")
);

CREATE UNIQUE INDEX uq_session_students_session_student ON attendance_session.session_students ("session_id", "student_id");

CREATE TABLE attendance_verification.attendance_records (
  "id" uuid,
  "session_id" uuid,
  "student_id" uuid,
  "recorded_by" uuid,
  "attendance_status" character varying(20),
  "record_source" character varying(20),
  "manual_reason" text,
  "created_at" timestamp with time zone,
  "updated_at" timestamp with time zone,
  PRIMARY KEY ("id"),
  CONSTRAINT "FK_attendance_records_recorded_by"
    FOREIGN KEY ("recorded_by")
      REFERENCES identity.users("id"),
  CONSTRAINT "FK_attendance_records_session_id"
    FOREIGN KEY ("session_id")
      REFERENCES attendance_session.sessions("id"),
  CONSTRAINT "FK_attendance_records_student_id"
    FOREIGN KEY ("student_id")
      REFERENCES academic.student_profiles("id")
);

CREATE UNIQUE INDEX uq_attendance_records_session_student ON attendance_verification.attendance_records ("session_id", "student_id");

CREATE TABLE academic.administrator_profiles (
  "id" uuid,
  "user_id" uuid NOT NULL,
  "first_name" character varying(100),
  "middle_name" character varying(100),
  "last_name" character varying(100),
  "department_id" uuid,
  "administrative_scope" character varying(30),
  "profile_status" character varying(20),
  "created_at" timestamp with time zone,
  "updated_at" timestamp with time zone,
  PRIMARY KEY ("id"),
  CONSTRAINT "FK_administrator_profiles_department_id"
    FOREIGN KEY ("department_id")
      REFERENCES academic.departments("id"),
  CONSTRAINT "FK_administrator_profiles_user_id"
    FOREIGN KEY ("user_id")
      REFERENCES identity.users("id")
);

CREATE UNIQUE INDEX uq_administrator_profiles_user_id ON academic.administrator_profiles ("user_id");

CREATE TABLE attendance_session.session_geofences (
  "session_id" uuid,
  "accuracy_buffer_m" numeric,
  "maximum_allowed_accuracy_m" numeric,
  "created_at" timestamp with time zone,
  "updated_at" timestamp with time zone,
  CONSTRAINT "FK_session_geofences_session_id"
    FOREIGN KEY ("session_id")
      REFERENCES attendance_session.sessions("id")
);

CREATE UNIQUE INDEX uq_session_geofences_session_id ON attendance_session.session_geofences ("session_id");

CREATE TABLE notification.notification_preferences (
  "user_id" uuid,
  "notification_type" character varying(50),
  "in_app_enabled" boolean,
  "push_enabled" boolean,
  "email_enabled" boolean,
  "updated_at" timestamp with time zone,
  PRIMARY KEY ("user_id", "notification_type"),
  CONSTRAINT "FK_notification_preferences_notification_type"
    FOREIGN KEY ("notification_type")
      REFERENCES notification.notification_types("code"),
  CONSTRAINT "FK_notification_preferences_user_id"
    FOREIGN KEY ("user_id")
      REFERENCES identity.users("id")
);

CREATE TABLE identity.role_permissions (
  "role_id" uuid,
  "permission_id" uuid,
  "assigned_at" timestamp with time zone,
  PRIMARY KEY ("role_id", "permission_id"),
  CONSTRAINT "FK_role_permissions_permission_id"
    FOREIGN KEY ("permission_id")
      REFERENCES identity.permissions("id"),
  CONSTRAINT "FK_role_permissions_role_id"
    FOREIGN KEY ("role_id")
      REFERENCES identity.roles("id")
);

CREATE TABLE identity.refresh_tokens (
  "id" uuid,
  "user_id" uuid,
  "token_hash" character varying(255),
  "issued_at" timestamp with time zone,
  "expires_at" timestamp with time zone,
  "revoked_at" timestamp with time zone,
  PRIMARY KEY ("id"),
  CONSTRAINT "FK_refresh_tokens_user_id"
    FOREIGN KEY ("user_id")
      REFERENCES identity.users("id")
);

CREATE UNIQUE INDEX uq_refresh_tokens_hash ON identity.refresh_tokens ("token_hash");

CREATE TABLE academic.lecturer_profiles (
  "id" uuid,
  "user_id" uuid NOT NULL,
  "employee_number" character varying(30),
  "first_name" character varying(100),
  "middle_name" character varying(100),
  "last_name" character varying(100),
  "department_id" uuid,
  "designation" character varying(100),
  "profile_status" character varying(20),
  "last_synced_at" timestamp with time zone,
  "created_at" timestamp with time zone,
  "updated_at" timestamp with time zone,
  PRIMARY KEY ("id"),
  CONSTRAINT "FK_lecturer_profiles_department_id"
    FOREIGN KEY ("department_id")
      REFERENCES academic.departments("id"),
  CONSTRAINT "FK_lecturer_profiles_user_id"
    FOREIGN KEY ("user_id")
      REFERENCES identity.users("id")
);

CREATE UNIQUE INDEX uq_lecturer_profiles_user_id ON academic.lecturer_profiles ("user_id");
CREATE UNIQUE INDEX uq_lecturer_profiles_employee_number ON academic.lecturer_profiles ("employee_number");

CREATE TABLE academic.course_lecturers (
  "id" uuid,
  "course_offering_id" uuid,
  "lecturer_id" uuid,
  "lecturer_role" character varying(30),
  "assigned_at" timestamp with time zone,
  "last_synced_at" timestamp with time zone,
  PRIMARY KEY ("id"),
  CONSTRAINT "FK_course_lecturers_course_offering_id"
    FOREIGN KEY ("course_offering_id")
      REFERENCES academic.course_offerings("id"),
  CONSTRAINT "FK_course_lecturers_lecturer_id"
    FOREIGN KEY ("lecturer_id")
      REFERENCES academic.lecturer_profiles("id")
);

CREATE UNIQUE INDEX uq_course_lecturers_offering_lecturer ON academic.course_lecturers ("course_offering_id", "lecturer_id");

COMMIT;
