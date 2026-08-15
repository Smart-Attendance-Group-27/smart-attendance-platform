# Local Application Database

This Compose project runs the UniAttend application PostgreSQL database. It is
separate from Keycloak's PostgreSQL database because each service owns different
data and migrations.

The database listens only on localhost and uses host port `5434` by default.
On the first start of an empty Docker volume, PostgreSQL applies:

1. `database/smart_attendance_db_clean.sql`
2. `database/migrations/0001_add_keycloak_user_id.sql`
3. `database/migrations/0002_add_session_geofence_snapshot.sql`
4. `database/smart_attendance_seed.sql`
5. `infra/local/application-db/demo_seed.sql`

The demo overlay does not insert geofence attempts or phone coordinates. It
creates two active sessions from the real seeded relationship chain:

| Session | ID | Purpose |
| --- | --- | --- |
| Geofence Demo - Near Centre | `40000000-0000-0000-0000-000000000001` | Expected pass when its centre is set to the demonstration location |
| Geofence Demo - Far Centre | `40000000-0000-0000-0000-000000000002` | Expected failure; its default centre is about 2.2 km north of Session A |

Both sessions include all six seeded CS3203 students. Their geofence policy is
a 60 m radius, 10 m accuracy buffer, and 50 m maximum accepted accuracy.

## Configure

Create the ignored local environment file from the template:

```powershell
Copy-Item infra/local/application-db/.env.example infra/local/application-db/.env
```

Set `APP_DB_PASSWORD` in that `.env` file to a local-only password. Do not use a
Supabase or production credential. The tracked example intentionally contains
no password.

## Start

Run from the repository root:

```powershell
docker compose --env-file infra/local/application-db/.env -f infra/local/application-db/docker-compose.yml up -d
```

Check that PostgreSQL is healthy:

```powershell
docker compose --env-file infra/local/application-db/.env -f infra/local/application-db/docker-compose.yml ps
```

Initialization scripts run only when the Docker volume is empty. Starting an
existing volume preserves its data and does not re-run migrations or seeds.

## Connect The Backend

Leave `DB_URI` unset and use these values in the backend's ignored `.env` file:

```dotenv
DB_HOST=localhost
DB_PORT=5434
DB_NAME=uniattend
DB_USER=uniattend
DB_PASSWORD=<same local-only password>
DB_SSL_MODE=disable
```

Open an interactive `psql` shell without placing the password on the command
line:

```powershell
docker compose --env-file infra/local/application-db/.env -f infra/local/application-db/docker-compose.yml exec application-db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

## Map A Local Keycloak Student

The application database cannot know a newly created Keycloak user's `sub` in
advance. Create one local user in the `uniattend` realm, assign the `student`
role, and copy its **User ID** from the Keycloak admin console. Then run this in
the `psql` shell:

```sql
\set keycloak_sub 'paste-local-keycloak-user-id-here'

UPDATE identity.users
SET keycloak_user_id = :'keycloak_sub',
    updated_at = now()
WHERE id = '20000000-0000-0000-0000-000000000011';
```

That application user owns the active `230701A` student profile and is eligible
for both demo sessions. Verify the mapping without printing any token:

```sql
SELECT u.email, u.keycloak_user_id, student.registration_number
FROM identity.users AS u
JOIN academic.student_profiles AS student ON student.user_id = u.id
WHERE u.id = '20000000-0000-0000-0000-000000000011';
```

## Set The Demonstration Location

The committed centres are deterministic sample values. Before a physical-phone
test, replace Session A's centre with the real demonstration location and keep
Session B at least one kilometre away. Only session configuration changes; the
phone must still submit a fresh real GPS reading.

```sql
\set near_latitude 6.795132
\set near_longitude 79.900421

UPDATE attendance_session.session_geofences
SET centre_latitude = :near_latitude,
    centre_longitude = :near_longitude,
    updated_at = now()
WHERE session_id = '40000000-0000-0000-0000-000000000001';

UPDATE attendance_session.session_geofences
SET centre_latitude = :near_latitude + 0.02,
    centre_longitude = :near_longitude,
    updated_at = now()
WHERE session_id = '40000000-0000-0000-0000-000000000002';
```

A latitude offset of `0.02` degrees is roughly 2.2 km. For a test location near
the poles, choose a known far centre instead.

## Verify Demo Data

Run in `psql`:

```sql
SELECT
  session.id,
  session.session_title,
  session.status,
  geofence.centre_latitude,
  geofence.centre_longitude,
  geofence.radius_m,
  (
    SELECT count(*)
    FROM attendance_session.session_students AS student
    WHERE student.session_id = session.id
  ) AS eligible_students
FROM attendance_session.sessions AS session
JOIN attendance_session.session_geofences AS geofence
  ON geofence.session_id = session.id
WHERE session.id IN (
  '40000000-0000-0000-0000-000000000001',
  '40000000-0000-0000-0000-000000000002'
)
ORDER BY session.id;
```

Expected: two active rows, complete snapshots, and six eligible students for
each session.

## Prepare A Repeat Demonstration

The seed makes both sessions active for seven days when an empty database
volume is initialized. Existing volumes keep their original timestamps. Before
a later demonstration, refresh only the two demo session windows in `psql`:

```sql
UPDATE attendance_session.sessions
SET scheduled_start_at = now() - INTERVAL '5 minutes',
    scheduled_end_at = now() + INTERVAL '7 days',
    check_in_opens_at = now() - INTERVAL '2 minutes',
    check_in_closes_at = now() + INTERVAL '7 days',
    late_after_at = now() + INTERVAL '15 minutes',
    status = 'active',
    activated_at = now() - INTERVAL '2 minutes',
    closed_at = NULL,
    cancelled_at = NULL,
    cancellation_reason = NULL,
    updated_at = now()
WHERE id IN (
  '40000000-0000-0000-0000-000000000001',
  '40000000-0000-0000-0000-000000000002'
);
```

Each student may submit at most three geofence attempts per session. To repeat
the demonstration for seeded student `230701A`, delete only that student's
attempts for the two demo sessions. This does not delete sessions, enrolments,
profiles, or attendance records:

```sql
BEGIN;

DELETE FROM attendance_verification.geofence_validation_attempts AS geofence
USING attendance_verification.verification_attempts AS verification
WHERE geofence.verification_attempt_id = verification.id
  AND verification.student_id = '23000000-0000-0000-0000-000000000001'
  AND verification.session_id IN (
    '40000000-0000-0000-0000-000000000001',
    '40000000-0000-0000-0000-000000000002'
  );

DELETE FROM attendance_verification.verification_attempts
WHERE student_id = '23000000-0000-0000-0000-000000000001'
  AND session_id IN (
    '40000000-0000-0000-0000-000000000001',
    '40000000-0000-0000-0000-000000000002'
  );

COMMIT;
```

## Verify Recorded Outcomes

After a phone attempt, inspect only the derived verification data. Exact phone
coordinates are neither stored nor selected:

```sql
SELECT
  session.session_title,
  verification.status AS verification_status,
  geofence.attempt_number,
  geofence.accuracy_m,
  geofence.distance_from_centre_m,
  geofence.validation_status,
  geofence.failure_reason,
  geofence.captured_at,
  geofence.validated_at
FROM attendance_verification.geofence_validation_attempts AS geofence
JOIN attendance_verification.verification_attempts AS verification
  ON verification.id = geofence.verification_attempt_id
JOIN attendance_session.sessions AS session
  ON session.id = verification.session_id
WHERE verification.student_id = '23000000-0000-0000-0000-000000000001'
  AND verification.session_id IN (
    '40000000-0000-0000-0000-000000000001',
    '40000000-0000-0000-0000-000000000002'
  )
ORDER BY geofence.validated_at DESC;
```

Prove that geofence validation did not create final attendance:

```sql
SELECT count(*) AS final_attendance_records
FROM attendance_verification.attendance_records
WHERE student_id = '23000000-0000-0000-0000-000000000001'
  AND session_id IN (
    '40000000-0000-0000-0000-000000000001',
    '40000000-0000-0000-0000-000000000002'
  );
```

Expected: `0` unless a separate attendance workflow previously created a
record for this student and session.

## Stop Or Reset

Stop containers while preserving the database:

```powershell
docker compose --env-file infra/local/application-db/.env -f infra/local/application-db/docker-compose.yml down
```

Delete local application data and re-run initialization on the next start:

```powershell
docker compose --env-file infra/local/application-db/.env -f infra/local/application-db/docker-compose.yml down -v
```

The `-v` command permanently deletes this local Docker volume. It does not
connect to or modify Supabase.
