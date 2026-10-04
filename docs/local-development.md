# Local development

This guide follows the development Compose file on `main`: Keycloak and its
own database run locally alongside Redis, Core, Face, and the web app. The
application PostgreSQL database is external. Commands use PowerShell; Docker
and npm commands also work in a POSIX shell.

## Application database

Use a development database that you can safely modify. Core and Face need
the UniAttend application schemas; a connection to an empty database is not enough.

For a **new, empty database**, apply:

1. `database/smart_attendance_db_clean.sql`.
2. Every forward `.sql` migration in `database/migrations/`, sorted by filename;
   exclude `*_rollback.sql`.
3. `database/smart_attendance_seed.sql` if you want development data.
4. The read-only `deployment/verify_mvp_schema.sql` gate.

Run SQL through the provider's editor or `psql` using an environment-supplied
connection. Do not replay the baseline or seeds against existing application
data. Existing databases need only migrations not already applied. CI's
[deployment workflow](../.github/workflows/deployment-ci.yml) shows the baseline,
forward-migration loop, and schema gate on a disposable database.

For external PostgreSQL, set `CORE_DB_URI` and `CORE_DB_SSL_MODE=require` in the
root `.env`. Percent-encode reserved characters in URI passwords, or leave
`CORE_DB_URI` blank and use the separate `CORE_DB_HOST`, `CORE_DB_PORT`,
`CORE_DB_NAME`, `CORE_DB_USER`, and `CORE_DB_PASSWORD` fields.

Leave `FACE_DB_URI` blank to inherit Core's connection; keep
`FACE_DB_SSL_MODE=require` for the same remote TLS database. A Supabase pooler
connection is supported; select the appropriate host, username, and port from
your own project. Do not copy another deployment's credentials.

The optional [local application database](../infra/local/application-db/README.md)
is a separate project. Its initialization list covers an earlier development
slice, so apply all remaining forward migrations before using current features.
It is not started by the root Compose file.

## Root environment

Copy `.env.example` to `.env`. Replace its old remote issuer values with:

```dotenv
KEYCLOAK_EXPECTED_ISSUER=http://localhost:8080/realms/uniattend
CORE_KEYCLOAK_JWKS_URL=http://keycloak:8080/realms/uniattend/protocol/openid-connect/certs
KEYCLOAK_AUDIENCE=uniattend-api
KEYCLOAK_AUTHORIZED_CLIENTS=uniattend-mobile,uniattend-web
KEYCLOAK_ADMIN_BASE_URL=http://keycloak:8080
KEYCLOAK_ADMIN_REALM=uniattend
KEYCLOAK_ADMIN_CLIENT_ID=uniattend-provisioner

WEB_BASE_URL=http://localhost:3000
WEB_KEYCLOAK_ISSUER=http://localhost:8080/realms/uniattend
WEB_KEYCLOAK_INTERNAL_ISSUER=http://keycloak:8080/realms/uniattend
WEB_KEYCLOAK_CLIENT_ID=uniattend-web
WEB_CORE_BACKEND_URL=http://core-api:8000

CORE_REDIS_URL=redis://redis:6379/0
FACE_VERIFICATION_SERVICE_URL=http://face-verification:8001
FACE_CORE_API_URL=http://core-api:8000
PUSH_WORKER_ENABLED=false
REMINDER_SCHEDULER_ENABLED=false
```

Also set `KEYCLOAK_ADMIN_PASSWORD`, `KEYCLOAK_DB_PASSWORD`,
`WEB_SESSION_SECRET`, `DYNAMIC_QR_HMAC_SECRET`,
`FACE_EMBEDDING_ENCRYPTION_KEY`, and both confidential client secrets.
The `local-keycloak` profile is required for the root project's Keycloak services.

Generate an independent value for each general secret:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

For a **fresh development face enrollment**, generate a Fernet-compatible key:

```powershell
python -c "import base64,secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
```

Copy generated values only into your ignored `.env`. If reusing encrypted
reference embeddings, obtain their **existing** key securely; generating a new
one makes those embeddings unreadable.

Check configuration without printing resolved environment values:

```powershell
docker compose --profile local-keycloak config --quiet
```

## Local accounts and identity mapping

Start only local infrastructure first:

```powershell
docker compose --profile local-keycloak up -d keycloak-db keycloak redis
```

Open `http://localhost:8080/admin` and sign in using the bootstrap administrator
username and password set in the root environment. Select the `uniattend` realm.

The realm template defines the three application roles, the mobile and web
clients, and a provisioning service account. It **does not contain human demo
users**. A Keycloak bootstrap administrator belongs to the management realm;
it is not an application administrator login.

1. Under **Clients → uniattend-web → Credentials**, obtain or regenerate the
   local client secret. Set `WEB_KEYCLOAK_CLIENT_SECRET` in the root environment.
2. Do the same for **uniattend-provisioner** and set
   `KEYCLOAK_ADMIN_CLIENT_SECRET`. Its service account has user-management
   permissions in the imported realm. This is required for application user
   provisioning.
3. Under **Users**, create a local application administrator, lecturer, or student
   with a complete name, enabled account, and an appropriate password.
4. Under the user's **Role mapping**, assign the corresponding realm role:
   `administrator`, `lecturer`, or `student`.
5. Copy the new user's Keycloak ID and link it to the intended application user
   in the **development** database.

Run a targeted update in your development database's SQL editor:

```sql
BEGIN;

UPDATE identity.users
SET keycloak_user_id = '<new-local-keycloak-user-id>'
WHERE id = '<existing-development-application-user-id>'
RETURNING id;

COMMIT;
```

Confirm exactly one intended row is returned. The application user must be active,
have the matching application role, and have its required active lecturer or
student profile. A student must also be enrolled in the offering used by the demo.
Keycloak role assignment alone does not create academic data.

Link one existing development administrator first. Once it can sign in, the
application's **Administrator → Users** workflow can provision other accounts
through the configured Keycloak service account. Academic management can then
create assignments, enrollments, classroom locations, and timetable entries.

Startup realm import skips an existing realm. To change client settings on an
existing local volume, use the admin console. Avoid deleting the volume simply
to update clients or users.

After setting secrets and mappings, start the application:

```powershell
docker compose up --build -d face-verification core-api web
docker compose --profile local-keycloak ps
```

## Android networking

The simplest shared issuer for browser and USB-device testing is
`http://localhost:8080/realms/uniattend`. ADB reverse lets the device use that
same origin while containers use Keycloak's internal DNS name for JWKS.

Copy `apps/mobile/.env.example` to `apps/mobile/.env` and override **all**
deployment URLs:

```dotenv
EXPO_PUBLIC_KEYCLOAK_ISSUER_URL=http://localhost:8080/realms/uniattend
EXPO_PUBLIC_KEYCLOAK_REALM=uniattend
EXPO_PUBLIC_KEYCLOAK_CLIENT_ID=uniattend-mobile
EXPO_PUBLIC_CORE_API_URL=http://localhost:8000
EXPO_PUBLIC_FACE_VERIFICATION_API_URL=http://localhost:8001
EXPO_PUBLIC_API_MODE=api
EXPO_PUBLIC_APP_TIMEZONE=Asia/Colombo
```

Connect a USB-debugging-enabled Android phone and accept its debugging prompt.
Run:

```powershell
adb devices
adb reverse tcp:8000 tcp:8000
adb reverse tcp:8001 tcp:8001
adb reverse tcp:8080 tcp:8080
adb reverse tcp:8081 tcp:8081

cd apps/mobile
npx expo run:android --device --no-bundler
npx expo start --dev-client --localhost --clear
```

The native app needs ML Kit; use a development build rather than Expo Go.
Rebuild after native dependency or native configuration changes. For JavaScript
changes, use the running development client. Restart Metro after changing public
environment variables. An installed EAS release does not receive new bundled
URLs simply because a local `.env` was edited.

<details>
<summary>Emulator or Wi-Fi alternatives</summary>

- **Emulator:** ADB reverse can use the same localhost configuration. Without
  reverse, `10.0.2.2` reaches the host, but the Keycloak issuer, web issuer,
  and backend's expected issuer must be configured consistently.
- **Phone over Wi-Fi:** use the workstation's LAN address for Core, Face,
  Keycloak, and the web base URL. Update the root expected issuer and web
  issuer, the mobile issuer, and the Keycloak web client's redirect URI,
  web origin, and logout redirect. Keep the container JWKS URL internal.
  Run `npx expo start --dev-client --host lan --clear`.
- The token's `iss` claim must match Core's expected issuer exactly.
  Different hostnames for the same local Keycloak can still produce a mismatch.
  Do not solve a mismatch by disabling issuer validation.

</details>

## Face enrollment and demo data

Use the administrator's **Users → Face enrollment** page to upload authorized
reference JPEG/PNG photos. Filenames identify existing students by registration
number. Enrollment creates encrypted embeddings in
`face_verification.student_face_profiles`; it does not create students or
attendance records.

The CLI accepts a **directory**, not a single image path:

```powershell
# From services/face-verification, with its own ignored .env configured:
python -m scripts.enroll_reference_faces <reference-photo-directory>
python -m scripts.enroll_reference_faces <reference-photo-directory> --commit
```

The first command is a dry run; the second performs enrollment. The Face
service's environment uses `DB_URI`, `FACE_EMBEDDING_ENCRYPTION_KEY`, and
`CORE_API_URL` rather than the root Compose-specific `CORE_DB_URI` name.
Keep reference photos out of the repository.

An attendance demo also needs an active course offering, student enrollment,
assigned lecturer, current timetable slot, and classroom geofence at the actual
test location. New sessions snapshot their location; editing the classroom later
does not move an existing session.

## Automated tests

JavaScript checks run from the repository root after `npm ci`:

```powershell
npm run typecheck --workspace=apps/web
npm run lint --workspace=apps/web
npm run test:ci --workspace=apps/web
npm run build --workspace=apps/web
npm run typecheck --workspace=apps/mobile
npm run lint --workspace=apps/mobile
npm run test:ci --workspace=apps/mobile
```

For each Python service, use a separate Python 3.12 virtual environment. For example:

```powershell
cd services/core-backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pytest -q
deactivate
```

Repeat from `services/face-verification` with its own virtual environment and
requirements. On Linux/macOS, activation is `source .venv/bin/activate`.

Backend CI intentionally does not supply live database environment variables.
Run unit tests in an isolated shell; a globally exported `DB_URI` can override
test settings. Native face dependencies need a supported Python build and
platform libraries; the [Face Dockerfile](../services/face-verification/Dockerfile)
lists its Linux packages. Automated suites do not replace physical-device
location, liveness, or push-delivery testing.

## Troubleshooting and stopping

| Symptom | First check |
| --- | --- |
| Keycloak realm is missing | The `local-keycloak` profile and import volume; startup import only creates absent realms |
| Login succeeds, but application data fails | Local Keycloak subject mapping, active application profile and role, issuer and JWKS |
| Web login fails | Confidential client secret and exact callback/logout URLs |
| User provisioning fails | Provisioner secret and service-account user-management roles |
| Face profile unavailable | Enrollment, existing embedding key, compatible model/version, active verification configuration |
| Location fails | Precise permission, reading accuracy, freshness, actual classroom coordinates, session snapshot |
| Inbox works but push is absent | Device permission, registered token, EAS/FCM credentials, worker flag and delivery receipts |
| Changed source is not reflected | Rebuild the relevant Docker service; dev Compose has no source bind mounts |

```powershell
docker compose logs --tail 100 core-api face-verification web
docker compose --profile local-keycloak down
```

Stopping preserves named database, Redis, and model volumes. Adding `-v` would
delete the project's local volumes and should only be used for a deliberate reset.
