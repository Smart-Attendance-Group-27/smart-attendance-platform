# Geofence Validation Physical-Phone Demo

This guide runs the complete local UniAttend geofence slice:

```text
Android phone -> Keycloak login -> active session -> fresh foreground GPS
-> authenticated FastAPI request -> PostgreSQL decision and attempt record
-> passed, failed, or retry-required mobile state
```

Use only local PostgreSQL. Nothing in this guide connects to Supabase, and no
password, access token, or phone coordinate belongs in Git or terminal logs.

## Demo Result

The finished demonstration proves that:

1. A student signs in through Keycloak using Authorization Code with PKCE.
2. The dashboard loads active sessions from FastAPI.
3. The phone captures a fresh foreground location after permission is granted.
4. FastAPI derives the student from the bearer token and checks eligibility.
5. FastAPI calculates the distance and stores the geofence attempt.
6. The near session passes and offers the face-verification placeholder.
7. The far session fails using the same real phone location.
8. A geofence pass does not create final attendance.

## 1. Preflight

Run from the repository root in PowerShell:

```powershell
git status --short
docker version
adb devices
```

Expected:

- Git has no unexpected local changes before setup.
- Docker Desktop is running.
- The physical Android phone is listed as `device`, not `unauthorized`.
- USB debugging is enabled and the authorization prompt was accepted.
- Location Services are enabled on the phone.

Install project dependencies if this checkout has not been prepared:

```powershell
npm install
$Python311 = "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe"
& $Python311 --version
& $Python311 -m venv services/core-backend/.venv
services\core-backend\.venv\Scripts\python.exe -m pip install -r services/core-backend/requirements.txt
```

Python 3.11, 3.12, or 3.13 from python.org is supported. Do not use the MSYS2
Python build. If python.org installed a supported version elsewhere, set
`$Python311` to that interpreter's full path.

## 2. Create Ignored Environment Files

### Application Database

```powershell
Copy-Item infra/local/application-db/.env.example infra/local/application-db/.env
```

Set `APP_DB_PASSWORD` to a new local-only password in that file. Do not reuse a
Supabase or production password.

### Core Backend

```powershell
Copy-Item services/core-backend/.env.example services/core-backend/.env
```

Use the local application database and localhost Keycloak settings:

```dotenv
DB_URI=
DB_HOST=localhost
DB_PORT=5434
DB_NAME=uniattend
DB_USER=uniattend
DB_PASSWORD=<same local-only password>
DB_SSL_MODE=disable

KEYCLOAK_EXPECTED_ISSUER=http://localhost:8080/realms/uniattend
KEYCLOAK_JWKS_URL=http://localhost:8080/realms/uniattend/protocol/openid-connect/certs
KEYCLOAK_AUDIENCE=uniattend-api
```

Keep the geofence defaults from `.env.example`: 30-second maximum reading age,
5-second future tolerance, and three attempts.

### Mobile

```powershell
Copy-Item apps/mobile/.env.example apps/mobile/.env.local
```

The tracked example already uses the USB-forwarded addresses:

```dotenv
EXPO_PUBLIC_KEYCLOAK_HOST=localhost
EXPO_PUBLIC_CORE_API_URL=http://localhost:8000
```

Verify all three files are ignored before adding local values:

```powershell
git check-ignore -v infra/local/application-db/.env
git check-ignore -v services/core-backend/.env
git check-ignore -v apps/mobile/.env.local
```

Each command must print an ignore rule. Stop if any command prints nothing.

## 3. Start Local Infrastructure

Start the application database and Keycloak from the repository root:

```powershell
docker compose --env-file infra/local/application-db/.env -f infra/local/application-db/docker-compose.yml up -d
docker compose --env-file infra/local/keycloak/.env.example -f infra/local/keycloak/docker-compose.yml up -d
```

Check both projects:

```powershell
docker compose --env-file infra/local/application-db/.env -f infra/local/application-db/docker-compose.yml ps
docker compose --env-file infra/local/keycloak/.env.example -f infra/local/keycloak/docker-compose.yml ps
curl.exe -I http://localhost:8080/realms/uniattend
```

The application database and Keycloak database should report healthy, and the
realm request should return HTTP 200.

PostgreSQL initialization runs only for an empty Docker volume. Existing
volumes preserve their previous data and timestamps.

## 4. Create And Link The Demo Student

Open `http://localhost:8080/admin` and sign in with the local development admin
account described in `infra/local/keycloak/README.md`.

1. Select the `uniattend` realm.
2. Create a user such as `student.demo`.
3. Set a non-temporary password under **Credentials**.
4. Assign the `student` realm role under **Role mapping**.
5. Copy the user's **ID** from the Details page. This is the Keycloak `sub`, not
   a password or access token.

Open the local application database shell:

```powershell
docker compose --env-file infra/local/application-db/.env -f infra/local/application-db/docker-compose.yml exec application-db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

Link that Keycloak user to seeded student `230701A`:

```sql
\set keycloak_sub 'paste-local-keycloak-user-id-here'

UPDATE identity.users
SET keycloak_user_id = :'keycloak_sub',
    account_status = 'active',
    updated_at = now()
WHERE id = '20000000-0000-0000-0000-000000000011';

SELECT
  users.email,
  users.keycloak_user_id IS NOT NULL AS is_linked,
  student.registration_number,
  users.account_status
FROM identity.users AS users
JOIN academic.student_profiles AS student ON student.user_id = users.id
WHERE users.id = '20000000-0000-0000-0000-000000000011';
```

Expected: one linked, active row for registration number `230701A`.

## 5. Prepare Near And Far Sessions

Use a maps application on the phone to drop a pin at the place where the
demonstration will happen. Copy its latitude and longitude. This configures the
session centre only; UniAttend must still capture a separate fresh reading from
the phone during check-in.

In the same `psql` shell, replace the sample values below:

```sql
\set near_latitude 6.795132
\set near_longitude 79.900421

UPDATE attendance_session.session_geofences
SET centre_latitude = :near_latitude,
    centre_longitude = :near_longitude,
    radius_m = 60,
    accuracy_buffer_m = 10,
    maximum_allowed_accuracy_m = 50,
    updated_at = now()
WHERE session_id = '40000000-0000-0000-0000-000000000001';

UPDATE attendance_session.session_geofences
SET centre_latitude = :near_latitude + 0.02,
    centre_longitude = :near_longitude,
    radius_m = 60,
    accuracy_buffer_m = 10,
    maximum_allowed_accuracy_m = 50,
    updated_at = now()
WHERE session_id = '40000000-0000-0000-0000-000000000002';
```

The latitude offset places Session B roughly 2.2 km from Session A.

Refresh both windows because an existing database volume may contain expired
seed timestamps:

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

Clear only this demo student's earlier attempts so the three-attempt policy
starts clean:

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

Verify two active sessions, complete snapshots, and six eligible students each:

```sql
SELECT
  session.id,
  session.session_title,
  session.status,
  session.check_in_opens_at <= now()
    AND session.check_in_closes_at >= now() AS check_in_open,
  geofence.radius_m,
  geofence.maximum_allowed_accuracy_m,
  count(student.id) AS eligible_students
FROM attendance_session.sessions AS session
JOIN attendance_session.session_geofences AS geofence
  ON geofence.session_id = session.id
LEFT JOIN attendance_session.session_students AS student
  ON student.session_id = session.id
WHERE session.id IN (
  '40000000-0000-0000-0000-000000000001',
  '40000000-0000-0000-0000-000000000002'
)
GROUP BY session.id, geofence.session_id
ORDER BY session.id;
```

Exit `psql` with `\q`.

## 6. Start FastAPI

Open a second PowerShell terminal at the repository root:

```powershell
services\core-backend\.venv\Scripts\python.exe -m uvicorn main:app --app-dir services/core-backend --reload --host 0.0.0.0 --port 8000
```

In another terminal, verify both health endpoints:

```powershell
curl.exe http://127.0.0.1:8000/health
curl.exe http://127.0.0.1:8000/health/db
```

Expected:

```json
{"status":"ok"}
{"status":"ok","database":"connected"}
```

The backend log may contain route, status, outcome, and reason metadata. It
must not contain tokens, database credentials, or exact phone coordinates.

## 7. Forward Android Ports Over USB

With the phone still connected and authorized:

```powershell
adb reverse tcp:8080 tcp:8080
adb reverse tcp:8000 tcp:8000
adb reverse tcp:8081 tcp:8081
adb reverse --list
```

These mappings let the phone use `localhost` for Keycloak, FastAPI, and Metro.
They also keep the Keycloak token issuer exactly equal to the backend's expected
issuer. USB mappings disappear when the device disconnects or restarts, so run
them again before the live demonstration.

If more than one Android device is connected, add `-s <device-serial>` after
`adb` in every command.

## 8. Build And Start The Mobile App

Because `expo-location` adds native code and permissions, rebuild the Android
development app at least once after pulling this branch. Regenerate the ignored
native project first so the `expo-location` config plugin updates the Android
manifest:

```powershell
Set-Location apps/mobile
npx.cmd expo prebuild --clean --platform android
npm.cmd run android
Set-Location ../..
```

The clean prebuild recreates only Expo's generated, Git-ignored native project.
The source of truth remains `apps/mobile/app.json`; do not make lasting manual
changes inside the generated `android` directory.

For later launches when that current development build is already installed:

```powershell
npm.cmd run start --workspace=apps/mobile -- --dev-client --clear
```

Keep Metro running. Do not use Expo Go for this demonstration.

On Android, open **Settings -> Apps -> UniAttend -> Permissions -> Location**
before the demo if an earlier denial was marked permanent. Set it to ask again
or allow only while using the app. UniAttend does not request background access.

## 9. Live Demonstration

### Login And Discovery

1. Start with UniAttend logged out.
2. Tap **Continue with university login**.
3. Sign in as the linked Keycloak student in the browser.
4. Confirm Keycloak redirects to UniAttend.
5. Confirm the dashboard displays **Geofence Demo - Near Centre** and
   **Geofence Demo - Far Centre**.

The FastAPI console should show successful requests to the protected active
session endpoint. Do not display or copy the bearer token.

### Near Session: Expected Pass

1. Stand close to the pin used as Session A's centre. Outdoors or near a window
   gives the most reliable accuracy.
2. Tap **Start attendance** on **Geofence Demo - Near Centre**.
3. Tap **Continue**.
4. Grant foreground location permission when Android asks.
5. Wait while the app obtains and submits the fresh reading.
6. Expect **Inside classroom area**.
7. Tap **Continue to Face Verification**.
8. Stop on the face-introduction screen. Geofencing only permits the next step;
   it does not complete face verification or attendance.

If the result requests a clearer location, wait outdoors for GPS accuracy to
improve and use **Check Again**. Do not exceed three attempts without resetting
the demo state.

### Far Session: Expected Failure

1. Return to the dashboard.
2. Tap **Start attendance** on **Geofence Demo - Far Centre**.
3. Tap **Continue** and wait for a new real reading.
4. Expect **Outside classroom area**.
5. Confirm there is no face-verification action for the failed result.

The phone location is real in both cases. Only the server-side session centre
is different.

## 10. Show PostgreSQL Evidence

Return to the `psql` shell and run:

```sql
SELECT
  session.session_title,
  verification.status AS verification_status,
  geofence.attempt_number,
  geofence.accuracy_m,
  round(geofence.distance_from_centre_m, 1) AS distance_m,
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
ORDER BY geofence.validated_at;
```

Expected:

- Near Centre has `PASSED`, measured accuracy, and a short distance.
- Far Centre has `FAILED`, `OUTSIDE_GEOFENCE`, and a distance near 2.2 km.
- Captured and validated timestamps are present.
- No submitted latitude or longitude is stored.

Prove that geofence validation alone created no attendance:

```sql
SELECT count(*) AS final_attendance_records
FROM attendance_verification.attendance_records
WHERE student_id = '23000000-0000-0000-0000-000000000001'
  AND session_id IN (
    '40000000-0000-0000-0000-000000000001',
    '40000000-0000-0000-0000-000000000002'
  );
```

Expected: `0`, provided no separate attendance workflow previously inserted a
record for this student and session.

Finally, log out of UniAttend and confirm protected attendance actions are no
longer visible.

## 11. Optional Retry-Required Proof

This uses a real phone reading but deliberately makes the server's accepted
accuracy policy restrictive. Reset the near-session attempts as shown in
section 5, then set:

```sql
UPDATE attendance_session.session_geofences
SET maximum_allowed_accuracy_m = 1,
    updated_at = now()
WHERE session_id = '40000000-0000-0000-0000-000000000001';
```

Run the near check again. An ordinary phone reading with accuracy worse than
1 metre should show **Location accuracy is too low** and **Check Again**.

Restore the normal policy immediately afterwards:

```sql
UPDATE attendance_session.session_geofences
SET maximum_allowed_accuracy_m = 50,
    updated_at = now()
WHERE session_id = '40000000-0000-0000-0000-000000000001';
```

## 12. Troubleshooting

| Symptom | Check | Resolution |
| --- | --- | --- |
| Phone cannot open Keycloak | `adb reverse --list` and port 8080 | Reconnect USB and repeat all three reverse commands |
| API shows 401 issuer error | Mobile host and `KEYCLOAK_EXPECTED_ISSUER` | With this USB setup, both must use `localhost` |
| API shows 401 audience error | Keycloak mobile audience mapper | Confirm `uniattend-api` is included in the access token audience |
| Dashboard cannot load | `/health/db`, port 8000 forwarding, backend console | Start FastAPI, fix local DB settings, then retry |
| Dashboard has no demo sessions | Session windows and student mapping | Repeat sections 4 and 5 |
| Location permission denied | Android app permissions | Allow Location only while using the app, then retry |
| Location services turned off | Android Location Services | Turn Location on, then retry |
| Accuracy remains too low | Physical GPS conditions | Move outdoors or near a window and wait briefly |
| Session unavailable after retries | Attempt count | Run the scoped reset in section 5 |
| Native module is missing | Installed development build predates `expo-location` | Run the Android rebuild command in section 8 |
| Android never asks for location | Generated manifest predates the location plugin | Run both the clean prebuild and Android build commands in section 8 |
| Metro does not connect | Port 8081 forwarding and Metro process | Repeat forwarding and restart Metro with `--clear` |
| Far session does not fail | Session centres | Reapply the `+ 0.02` latitude update in section 5 |

## 13. Automated Verification

Backend tests, from the repository root:

```powershell
Set-Location services/core-backend
.\.venv\Scripts\python.exe -m pytest
Set-Location ../..
```

Mobile checks:

```powershell
npm.cmd run test:ci --workspace=apps/mobile
npm.cmd run typecheck --workspace=apps/mobile
npm.cmd run lint --workspace=apps/mobile
```

The test suites use fake locations, in-memory JWKS, and local test seams. They
do not read the computer's GPS or contact external services.

## Demo Checklist

- [ ] Local application database and Keycloak are healthy.
- [ ] Demo student is linked to `230701A` and belongs to both sessions.
- [ ] Near and far centres match tomorrow's demonstration location.
- [ ] Session windows are open and previous attempts are cleared.
- [ ] Backend health and database health return 200.
- [ ] Ports 8080, 8000, and 8081 are USB-forwarded.
- [ ] Current Android development build includes `expo-location`.
- [ ] Student logs in through Keycloak and sees both sessions.
- [ ] Near session passes and offers only the face-verification next step.
- [ ] Far session fails using a new real phone reading.
- [ ] PostgreSQL shows both derived attempt records.
- [ ] Final attendance count remains zero.
- [ ] Logout removes access to protected attendance actions.
