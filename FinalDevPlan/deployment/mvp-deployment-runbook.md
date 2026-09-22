# First MVP deployment runbook

**Release scope:** Deploy the current web, Core API, face service and Redis containers against external PostgreSQL and Keycloak. Liveness remains under development and is explicitly disabled in this first deployment.

## Scope boundary

- Create pilot attendance sessions with **Require face verification turned off**. The web form currently defaults it on, so the lecturer must clear that option for every pilot session.
- Geofence, QR, session lifecycle, manual attendance, policy, reports and administrator workflows can be exercised normally.
- The face service is deployed so its process, database connection, model startup, enrollment tooling and non-liveness readiness comparison can be tested separately. A readiness pass is not proof of spoof-resistant attendance.
- Push workers and reminders default off. Enable them only after the notification migrations, Expo credentials and physical Android delivery are verified.

## Required external services

1. A PostgreSQL target reachable by both Python services.
2. A Keycloak realm reachable from containers, browsers and Android.
3. DNS and HTTPS ingress for web, Core API and face-service readiness endpoints.
4. A deployment host with Docker Engine and Docker Compose v2, or a platform capable of building the three Dockerfiles with the same environment contract.

The production Compose file does not start a development Keycloak or application PostgreSQL. It binds application ports to `127.0.0.1` by default so a TLS reverse proxy on the host can publish them safely.

## 1. Freeze and configure

Use a reviewed commit SHA as the image tag:

```powershell
Copy-Item deployment/mvp.env.example deployment/mvp.env
```

Replace every placeholder in `deployment/mvp.env`. Generate independent secrets rather than copying development values:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

The first command can be used separately for `WEB_SESSION_SECRET` and `DYNAMIC_QR_HMAC_SECRET`. Keep `FACE_EMBEDDING_ENCRYPTION_KEY` stable after reference embeddings are created; changing it without re-encryption makes existing embeddings unreadable.

Validate without printing secret values:

```powershell
python deployment/validate_env.py deployment/mvp.env
docker compose --env-file deployment/mvp.env -f docker-compose.production.yml config --quiet
```

Configure Keycloak with:

- Web redirect URI: `<WEB_BASE_URL>/api/auth/callback`
- Web post-logout URI: `<WEB_BASE_URL>/login`
- Mobile redirect scheme: `uniattend://`
- API audience: the value of `KEYCLOAK_AUDIENCE`
- Active `student`, `lecturer` and `administrator` roles
- A confidential web client and a service-account client for account provisioning

## 2. Back up and prepare PostgreSQL

Take and verify a restorable backup before modifying an existing database. Use the migration ledger and read-only schema queries to decide which files are missing. Apply missing forward migrations in filename order with `ON_ERROR_STOP=1`; do not re-run non-idempotent migrations blindly.

For a new database, apply:

1. `database/smart_attendance_db_clean.sql`
2. Every non-rollback file under `database/migrations/` in filename order
3. Approved pilot data only; do not load the general development seed into a production-like target

Verify the result:

```powershell
$mvpSettings = Get-Content deployment/mvp.env -Raw | ConvertFrom-StringData
psql $mvpSettings.CORE_DB_URI -v ON_ERROR_STOP=1 -f deployment/verify_mvp_schema.sql
Remove-Variable mvpSettings
```

The final query reports whether face readiness has an active threshold and how many encrypted reference profiles exist. Those values are informative for the readiness test; they do not block sessions with face verification disabled.

## 3. Build and start

```powershell
docker compose --env-file deployment/mvp.env -f docker-compose.production.yml build --pull
docker compose --env-file deployment/mvp.env -f docker-compose.production.yml up -d
docker compose --env-file deployment/mvp.env -f docker-compose.production.yml ps
```

The face container's first startup may download the configured InsightFace model. Its named cache volume preserves that model between container replacements. Face readiness does not block the Core API because face attendance is outside this release; the web waits for Core API database health.

Publish the three loopback ports through HTTPS ingress, then run:

```powershell
python deployment/smoke_test.py deployment/mvp.env
```

This checks web reachability, both process and database health endpoints, and Keycloak discovery.

## 4. Build the Android pilot

Set these values in the EAS build environment from the matching entries in `deployment/mvp.env`:

- `EXPO_PUBLIC_CORE_API_URL`
- `EXPO_PUBLIC_FACE_VERIFICATION_API_URL`
- `EXPO_PUBLIC_KEYCLOAK_ISSUER_URL`
- `EXPO_PUBLIC_KEYCLOAK_REALM`
- `EXPO_PUBLIC_KEYCLOAK_CLIENT_ID`

Build an internal Android artifact from the same release commit. Install it on a physical device and verify login, session discovery, geofence, QR, attendance progress and sign-out. Keep face verification off on pilot sessions until liveness integration is delivered.

## 5. Pilot checks

1. Administrator login, account provisioning and academic data reads.
2. Lecturer creates a session with face verification off, then activates it.
3. Student discovers the active session and completes the configured geofence step.
4. Student completes initial check-in and QR progress when QR is enabled.
5. Lecturer sees the same state, applies a manual result, closes or cancels a test session, and checks reports.
6. If notification workers are later enabled, test registration, all delivery triggers, retry behavior and deep links separately.
7. For face readiness only, enroll an approved pilot photo, activate an evaluated test threshold and run the readiness capture. Do not use that result for attendance in this release.

Record the commit SHA, image IDs, Android build, migration verification output, tester, device and result for every check.

## 6. Operations and rollback

Inspect health and bounded container logs:

```powershell
docker compose --env-file deployment/mvp.env -f docker-compose.production.yml ps
docker compose --env-file deployment/mvp.env -f docker-compose.production.yml logs --since 15m
```

For an application failure, redeploy the last known-good image tag. Disable push and reminder workers first if they are creating incorrect or repeated messages. Preserve logs and database evidence.

Treat database rollback separately. Assess writes made since release and restore the tested backup when necessary; do not automatically run rollback SQL against live attendance data.

Stop the stack without deleting persistent caches:

```powershell
docker compose --env-file deployment/mvp.env -f docker-compose.production.yml down
```

Do not add `-v` during an incident because it deletes the Redis and face-model cache volumes.
