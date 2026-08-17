# Smart Attendance Platform

UniAttend is a monorepo for university attendance workflows:

- `apps/web` - Next.js lecturer QR test/dashboard app
- `apps/mobile` - Expo React Native student app
- `services/core-backend` - FastAPI core API
- `services/face-verification` - separate FastAPI face-verification service
- `infra/local/keycloak` - local Keycloak realm import files
- `database` - SQL schema, migrations and seed files

The Docker setup runs the server-side development environment. The Expo mobile
app is not Dockerized and should keep running on an Android emulator or a real
Android phone.

## Prerequisites

- Docker Desktop
- Node.js and npm, for running the mobile app outside Docker
- Android Studio / Android platform tools, for emulator or physical-device work
- Supabase PostgreSQL credentials for the main application database

## Docker Services

The root `docker-compose.yml` starts:

- Next.js web app
- FastAPI core backend
- FastAPI face-verification service
- Redis
- Keycloak
- Keycloak PostgreSQL database

It does not start:

- Expo / React Native mobile app
- Main Supabase PostgreSQL database

## Environment Setup

Create a local root env file:

```powershell
Copy-Item .env.example .env
```

Fill in `.env` with local values. Do not commit `.env`.

Important variables:

```text
CORE_DB_URI
CORE_DB_HOST
CORE_DB_PORT
CORE_DB_NAME
CORE_DB_USER
CORE_DB_PASSWORD
CORE_DB_SSL_MODE

FACE_DB_URI
FACE_DB_HOST
FACE_DB_PORT
FACE_DB_NAME
FACE_DB_USER
FACE_DB_PASSWORD
FACE_DB_SSL_MODE

DYNAMIC_QR_HMAC_SECRET

KEYCLOAK_ADMIN_USERNAME
KEYCLOAK_ADMIN_PASSWORD
KEYCLOAK_DB_NAME
KEYCLOAK_DB_USER
KEYCLOAK_DB_PASSWORD
KEYCLOAK_EXPECTED_ISSUER
KEYCLOAK_AUDIENCE

WEB_PORT
CORE_API_PORT
FACE_VERIFICATION_PORT
KEYCLOAK_HTTP_PORT
REDIS_PORT
```

`CORE_DB_URI` points to the external Supabase database. If `CORE_DB_URI` is set,
the separate `CORE_DB_*` fields are ignored by the backend.

`FACE_DB_URI` is optional. If it is blank, Docker Compose passes the core
database settings to the face-verification service.

Generate a local dynamic QR secret with:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

## Start Docker Environment

From the repository root:

```powershell
docker compose up --build
```

To run in the background:

```powershell
docker compose up --build -d
```

Check status:

```powershell
docker compose ps
```

Stop containers:

```powershell
docker compose down
```

Stop containers and remove local Redis/Keycloak database volumes:

```powershell
docker compose down -v
```

## Service URLs

Default local URLs:

```text
Web app:                  http://localhost:3000
QR test page:             http://localhost:3000/qr-test
Core API:                 http://localhost:8000
Core API health:          http://localhost:8000/health
Core API DB health:       http://localhost:8000/health/db
Face service:             http://localhost:8001
Face service health:      http://localhost:8001/health
Keycloak:                 http://localhost:8080
Keycloak admin console:   http://localhost:8080/admin
Redis:                    localhost:6379
Keycloak PostgreSQL:      localhost:5433
```

The web container calls the backend through Docker networking:

```text
http://core-api:8000
```

The core backend calls Redis through Docker networking:

```text
redis://redis:6379/0
```

The core backend can address the face-verification service through:

```text
http://face-verification:8001
```

The core backend fetches Keycloak JWKS through Docker networking:

```text
http://keycloak:8080/realms/uniattend/protocol/openid-connect/certs
```

## Keycloak Notes

The Keycloak realm import comes from:

```text
infra/local/keycloak/realm
```

`KEYCLOAK_EXPECTED_ISSUER` must match the issuer in the access token exactly.
That issuer depends on the URL the browser or mobile app uses to reach
Keycloak.

For browser-only local testing, this is usually:

```text
http://localhost:8080/realms/uniattend
```

For Android emulator testing, use the emulator-accessible host in the mobile
configuration, usually:

```text
http://10.0.2.2:8080/realms/uniattend
```

For a physical phone over Wi-Fi, use your laptop IPv4 address:

```text
http://YOUR_LAPTOP_IP:8080/realms/uniattend
```

If the mobile login URL changes, update `KEYCLOAK_EXPECTED_ISSUER` and restart
the `core-api` container.

## Android Access

The mobile app runs outside Docker.

For Android emulator, set `apps/mobile/.env` like:

```text
EXPO_PUBLIC_KEYCLOAK_HOST=10.0.2.2
EXPO_PUBLIC_CORE_API_URL=http://10.0.2.2:8000
```

For a physical phone on the same Wi-Fi, use the laptop IPv4 address:

```text
EXPO_PUBLIC_KEYCLOAK_HOST=YOUR_LAPTOP_IP
EXPO_PUBLIC_CORE_API_URL=http://YOUR_LAPTOP_IP:8000
```

For a physical phone connected by USB with ADB reverse:

```powershell
adb reverse tcp:8000 tcp:8000
adb reverse tcp:8080 tcp:8080
adb reverse tcp:8081 tcp:8081
```

Then use:

```text
EXPO_PUBLIC_KEYCLOAK_HOST=127.0.0.1
EXPO_PUBLIC_CORE_API_URL=http://127.0.0.1:8000
```

Start the mobile dev client from `apps/mobile`:

```powershell
npx.cmd expo start --dev-client --host lan --clear
```

Rebuild/reinstall the Android app only when native dependencies or native config
change:

```powershell
npx.cmd expo run:android --device
```

## QR Test Flow

1. Start Docker:

```powershell
docker compose up --build
```

2. Open:

```text
http://localhost:3000/qr-test
```

3. Use the development attendance session ID:

```text
40000000-0000-0000-0000-000000000001
```

4. Create either a static or dynamic QR session.

5. Scan the QR from the mobile app after the face-verification screen.

The mobile app sends:

```http
POST /api/v1/qr-sessions/{qrSessionId}/verify
```

with:

```json
{
  "qrValue": "scanned-raw-qr-value"
}
```

## Useful Commands

Docker logs:

```powershell
docker compose logs -f core-api
docker compose logs -f web
docker compose logs -f keycloak
```

Restart one service:

```powershell
docker compose restart core-api
```

Rebuild one service:

```powershell
docker compose build core-api
docker compose up -d core-api
```

Run JavaScript checks outside Docker:

```powershell
npm.cmd run typecheck --workspace=apps/mobile
npm.cmd run test:ci --workspace=apps/mobile
npm.cmd run lint --workspace=apps/mobile
npm.cmd run lint --workspace=apps/web
npm.cmd run build --workspace=apps/web
```

Run backend tests outside Docker:

```powershell
cd services/core-backend
python -m pytest tests
```

Run face-verification tests outside Docker:

```powershell
cd services/face-verification
python -m pytest tests
```

## Docker Networking

Inside Docker Compose, containers use service names:

```text
web -> core-api:8000
core-api -> redis:6379
core-api -> keycloak:8080
core-api -> face-verification:8001
keycloak -> keycloak-db:5432
```

From your browser or Android device, use the host-published ports:

```text
localhost:3000
localhost:8000
localhost:8080
```

The Android emulator cannot use container service names. Use `10.0.2.2` to reach
services published on the host machine.
