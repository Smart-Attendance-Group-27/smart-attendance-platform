# Face Verification Service

Face detection, liveness, quality assessment, embedding generation, and face
matching service for the UniAttend smart attendance platform.

## Status

The service currently includes the database integration, encrypted reference
enrollment, InsightFace analysis adapter, similarity comparison, readiness
verification service, and the readiness HTTP endpoint. Production threshold
evaluation, liveness verification, attendance-session orchestration, and
deployment hardening remain incomplete.

Reference enrollment will be performed by authorized university
administrators using existing official university student ID photographs.
Before real attendance sessions begin, students will be given a readiness
period in which they can complete trial face verification without creating or
changing any attendance record.

## Responsibilities

The service will:

- Validate that a capture contains exactly one usable face.
- Evaluate image quality.
- Perform the approved liveness check.
- Generate an embedding with the same model and preprocessing used before
  verification.
- Ask the Core Backend to authenticate the caller and resolve the active
  student profile, then retrieve that student's reference embedding.
- Compare the capture embedding with the reference embedding.
- Return a typed verification result.
- Record validation metadata without storing the raw verification capture.
- Support attendance-independent readiness checks using the same approved
  verification pipeline.

The service will not:

- Issue credentials, manage Keycloak sessions, or validate Keycloak tokens
  itself. The Core Backend owns those responsibilities.
- Trust a student ID supplied by the mobile client.
- Return reference embeddings to the mobile application.
- Determine attendance status such as On-time or Late.
- Store raw face captures unless a separately approved retention policy
  requires it.

## Request Flows

Readiness checks currently use the standalone service directly:

```text
Mobile application
    -> Keycloak issues an access token
    -> Face Verification Service forwards the token to the Core Backend
    -> Core Backend validates the token and returns the active student profile
    -> Face Verification Service processes the capture
    -> Face Verification Service records the readiness result
```

Attendance verification is coordinated by the Core Backend:

```text
Mobile application
    -> Core Backend authenticates the student and validates the session
    -> Core Backend creates or finds the attendance verification attempt
    -> Face Verification Service processes the capture
    -> Face Verification Service records the face-validation attempt
    -> Core Backend maps the result to the mobile response
```

Attendance marking must communicate through the Core Backend. The readiness
endpoint may be called by the mobile app because it does not create or modify
attendance, but it still requires a valid student Keycloak access token.

The platform has three distinct face-verification workflows:

```text
Administrator enrollment -> Create or replace the reference embedding
Student readiness check   -> Confirm verification works without attendance
Attendance verification  -> Verify identity during a real attendance session
```

Enrollment and readiness checks must never create an attendance record or mark
a student On-time, Late, Present, or Absent.

## Public API Contract

The implemented Core Backend endpoint is:

```http
POST /api/v1/attendance-sessions/{session_id}/face-verifications
Authorization: Bearer <access-token>
Content-Type: multipart/form-data

image: <JPEG or PNG image>
```

The authenticated access token determines the student identity. The request
must not accept a client-controlled `student_id`.

The public response should preserve the statuses already supported by the
mobile application:

```json
{ "status": "success", "attemptNumber": 1, "canRetry": false }
```

Failure statuses are `face_not_detected`, `multiple_faces`, and
`verification_failure`. Each response includes `attemptNumber` and `canRetry`
so the app can stop offering another capture after the configured limit.

Transport, authentication, configuration, and unexpected server failures
should use appropriate HTTP error responses. Raw exceptions, embeddings,
internal IDs, model diagnostics, and security-sensitive scores must not be
returned to the mobile client.

### Readiness check

The implemented student readiness endpoint is:

```http
POST /api/v1/face-verification/readiness
Authorization: Bearer <access-token>
Content-Type: multipart/form-data

image: <JPEG or PNG image>
```

The readiness endpoint uses the authenticated student identity and does not
accept an attendance session ID. A successful response confirms that the
student's reference profile and the current capture can pass the approved
verification pipeline:

```json
{ "status": "passed", "message": "Face readiness verification passed" }
```

Other expected statuses include:

```json
{ "status": "profile_not_enrolled" }
```

```json
{ "status": "no_face", "message": "No face was detected" }
```

```json
{ "status": "multiple_faces", "message": "More than one face was detected" }
```

```json
{ "status": "liveness_failure" }
```

```json
{ "status": "verification_failure" }
```

Readiness results are diagnostic only. They must not create an
`attendance_verification.verification_attempts` row or update attendance.

## Enrollment Flow

Reference embeddings are generated from existing official university student
ID photographs. Enrollment is initiated only by an authorized university
administrator through an authenticated administrative workflow.

The enrollment system must resolve the university student ID to the existing
`academic.student_profiles.id`. It must not create a profile from an
unvalidated client-supplied database UUID.

The controlled enrollment process is:

```text
Authorized administrator starts enrollment
    -> Resolve and validate the university student ID
    -> Retrieve or securely receive the official university ID photograph
    -> Detect exactly one face
    -> Validate image quality
    -> Align and preprocess the face
    -> Generate the embedding
    -> Normalize the embedding if required by the selected model
    -> Store the embedding with model metadata
    -> Delete the source image according to the approved retention policy
```

Enrollment and verification must use the same:

- Model and model version
- Embedding dimension
- Face alignment and preprocessing rules
- Normalization method
- Similarity metric

Embeddings generated by incompatible models or preprocessing versions must not
be compared.

The original ID photograph remains governed by the university's approved
identity system. Any temporary copy used by UniAttend must be protected and
deleted after embedding generation according to the approved retention policy.
Administrators must not be able to view or download the generated embedding.

### Administrator batch enrollment script

The service includes a local administrator CLI for official photographs named
with the student's exact registration number, for example:

```text
approved-reference-photos/
    230734J.png
    230735K.jpg
```

Run it from `services/face-verification`. It performs a safe dry run by default:

```powershell
python -m scripts.enroll_reference_faces "C:\path\to\approved-reference-photos"
```

The dry run checks that each filename resolves to one active row in
`academic.student_profiles`. It does not load InsightFace or write embeddings.
After reviewing the summary, explicitly enable database writes:

```powershell
python -m scripts.enroll_reference_faces "C:\path\to\approved-reference-photos" --commit
```

The script accepts `.jpg`, `.jpeg`, and `.png` files directly inside the
specified directory. It skips duplicate registration numbers, inactive
students, revoked profiles, and profiles that are already enrolled. It never
prints an embedding or database secret.

The current development schema stores embeddings as a PostgreSQL array. Do not
use this script with genuine student data until the approved embedding
encryption, key-management, model-metadata, authorization, audit, and source
photo retention controls are implemented.

## Readiness Period

The university will provide an initial readiness period before real attendance
sessions begin. Every enrolled student can perform one or more trial
verifications to confirm that their reference profile and device capture work
with the selected model, liveness method, quality checks, and active
configuration.

```text
Administrator creates reference embedding from the official ID photo
    -> Student signs in during the readiness period
    -> Student completes a trial capture and liveness check
    -> Shared verification pipeline compares the embeddings
    -> Readiness result is recorded
    -> No attendance record or attendance status is created
```

Recommended readiness states are:

- `not_checked`
- `ready`
- `action_required`

A failed readiness check should provide safe guidance and allow a controlled
retry. Repeated failures should direct the student to university support or an
administrator-managed re-enrollment process. They must not count as absence or
failed attendance.

The readiness and attendance flows reuse the same face-processing pipeline but
have different coordination and persistence behavior:

```text
Shared detection, quality, liveness, embedding, and comparison pipeline
|-- Readiness coordinator  -> readiness result only
`-- Attendance coordinator -> attendance verification result
```

## Verification Flow

```text
Captured image or approved liveness input
    -> Validate input type and size
    -> Perform liveness evaluation
    -> Detect exactly one face
    -> Validate quality
    -> Align and preprocess
    -> Generate capture embedding
    -> Retrieve reference embedding and active configuration
    -> Compare embeddings
    -> Persist validation metadata
    -> Discard the raw capture
    -> Return the typed result
```

Liveness and identity matching are separate checks. A high similarity score
must not bypass a failed liveness check.

## Database Model

The current schema is defined in:

```text
database/smart_attendance_db_clean.sql
```

### `face_verification.face_profiles`

Stores one reference face profile per student:

- `id`
- `student_id`
- `embedding` (`double precision[]` in the current schema)
- `embedding_generation_status`
- `failure_reason`
- `generated_at`
- `created_at`
- `updated_at`

`student_id` is unique and references `academic.student_profiles`.

Before production use, the schema should record at least the model name,
model version, embedding dimension, and preprocessing version. The team should
also decide whether to retain `double precision[]` or migrate to a fixed-size
`pgvector` column after choosing the model.

### `face_verification.verification_configs`

Stores versioned verification thresholds:

- `id`
- `similarity_threshold`
- `is_active`
- `configured_by`
- `effective_from`
- `created_at`

The selected similarity threshold is meaningful only for the evaluated model,
preprocessing pipeline, normalization method, and similarity metric. Model and
metric metadata should therefore be added before activation.

### `face_verification.face_validation_attempts`

Stores the current attendance face-verification outcome and diagnostic
metadata:

- `verification_attempt_id`
- `face_profile_id`
- `attempt_number`
- `liveness_passed`
- `quality_passed`
- `similarity_score`
- `verification_config_id`
- `validation_status`
- `failure_reason`
- `captured_at`
- `validated_at`

The parent `attendance_verification.verification_attempts` table connects the
attempt to the attendance session and authenticated student.

Attendance retries update the same face-validation row for that parent
verification attempt. A successful result is retained immediately; otherwise
the row contains the latest attempt and becomes the final failed result when
the retry limit is reached. This avoids storing one row per capture for the
same student and session.

Do not store the raw capture, access token, or reference embedding in attempt
logs.

### Proposed readiness data

Readiness checks do not belong in
`attendance_verification.verification_attempts`, because that table requires a
real attendance session. The ERD should add a separate table such as
`face_verification.readiness_check_attempts` containing:

- `id`
- `student_id`
- `face_profile_id`
- `verification_config_id`
- `attempt_number`
- `liveness_passed`
- `quality_passed`
- `similarity_score`
- `status`
- `failure_reason`
- `captured_at`
- `validated_at`

The team may also add `readiness_status` and
`last_readiness_checked_at` to `face_profiles` as a current summary. Attempt
history remains in the separate readiness table. No readiness table should
reference or fabricate an attendance session.

## Intended Project Structure

```text
services/face-verification/
|-- main.py
|-- Dockerfile
|-- requirements.txt
|-- .env.example
|-- core/
|   |-- config.py
|   |-- logging.py
|   `-- security.py
|-- api/
|   `-- routes.py
|-- models/
|   |-- requests.py
|   `-- responses.py
|-- services/
|   |-- detection.py
|   |-- quality.py
|   |-- liveness.py
|   |-- embedding.py
|   `-- verification.py
`-- tests/
    |-- unit/
    `-- integration/
```

Create these files only as their responsibilities are implemented. Empty
folders do not need to be committed.

## Configuration

Exact environment variables will be defined after the model and deployment
architecture are approved. The service is expected to require configuration
for:

- Database connection
- Internal service authentication
- Model name and version
- Model artifact path or identifier
- Maximum capture size
- Similarity metric and active configuration lookup
- Liveness and quality settings
- Request timeout and structured logging

Secrets must be stored in local environment files or deployment secret stores.
Never commit credentials, access tokens, biometric data, or model-provider
secrets.

## Security and Privacy

Face embeddings are biometric data and must be protected accordingly.

- Require authenticated and authorized requests.
- Resolve student identity from trusted authentication context.
- Encrypt network traffic outside local development.
- Restrict database access to the minimum required service role.
- Avoid logging raw images, embeddings, access tokens, or full similarity
  vectors.
- Enforce input type, file-size, resolution, and timeout limits.
- Process captures in memory where practical and discard them promptly.
- Define consent, enrollment, re-enrollment, revocation, and deletion policies.
- Restrict official ID-photo enrollment and re-enrollment to authorized
  university administrators.
- Audit which administrator initiated enrollment without logging the photo or
  embedding.
- Keep readiness results separate from attendance and academic penalties.
- Record configuration and model versions for auditability.
- Rate-limit verification attempts and coordinate retry limits with the Core
  Backend.

## Testing Strategy

Unit tests should cover:

- No face, one face, and multiple faces
- Quality pass and failure
- Liveness pass and failure
- Embedding normalization and dimension validation
- Similarity calculation at, below, and above the configured threshold
- Model-version mismatch
- Missing, failed, or revoked face profiles
- Inactive or missing verification configuration
- Safe exception mapping and capture cleanup
- Readiness success and each safe readiness failure status
- Confirmation that readiness checks never create attendance records

Integration tests should cover:

- Authenticated Core Backend to face-service communication
- Database reads and attempt recording
- Deterministic enrollment and verification fixtures
- Authorized administrator enrollment and rejected unauthorized enrollment
- Readiness checks with and without an enrolled reference profile
- Rejected malformed, oversized, and unsupported captures
- Confirmation that raw captures and embeddings are absent from logs

Model evaluation must use a separately approved dataset and report false
acceptance and false rejection behavior before activating a threshold.
