# UniAttend Mobile

Expo mobile application for UniAttend student attendance.

## Geofence Demonstration

The attendance check-in captures one fresh, high-accuracy foreground location
reading and sends it to the Core API. The phone does not calculate the distance
or decide whether the student passed. No background-location permission or
last-known location is used.

For the complete local PostgreSQL, Keycloak, FastAPI, USB forwarding, and
physical-phone walkthrough, see
[`docs/geofence-validation-demo.md`](../../docs/geofence-validation-demo.md).

## Shared Keycloak Login

The mobile app uses Keycloak for credential entry. The app must not collect and
submit a student's university password directly.

For normal team development, point the app at the shared deployed Keycloak
realm:

```text
EXPO_PUBLIC_KEYCLOAK_ISSUER_URL=https://keycloak-production-be79.up.railway.app/realms/Uni%20Attend
EXPO_PUBLIC_KEYCLOAK_REALM="Uni Attend"
EXPO_PUBLIC_KEYCLOAK_CLIENT_ID=uniattend-mobile
```

Do not put passwords, tokens or client secrets in `EXPO_PUBLIC_*` variables;
the mobile client is public and uses Authorization Code Flow with PKCE.

The Core API still runs locally during development. For Android emulator
testing, use:

```text
EXPO_PUBLIC_CORE_API_URL=http://10.0.2.2:8000
```

For physical Android phone testing over Wi-Fi, use the computer's LAN IP for
the Core API:

```text
EXPO_PUBLIC_CORE_API_URL=http://192.168.1.25:8000
```

Replace `192.168.1.25` with the IPv4 address shown by `ipconfig` on the
computer running the FastAPI backend. Restart Expo after changing env values.

## Local Keycloak Fallback

If you are intentionally testing against the local Docker Keycloak realm,
leave `EXPO_PUBLIC_KEYCLOAK_ISSUER_URL` blank and use:

```text
EXPO_PUBLIC_KEYCLOAK_HOST=10.0.2.2
```

For local Keycloak on the Android emulator, the resolved issuer is:

```text
http://10.0.2.2:8080/realms/uniattend
```

`10.0.2.2` is the Android emulator address for the host machine where Docker is
running.

## Start Local Keycloak

Run this from the repository root:

```powershell
docker compose --env-file infra/local/keycloak/.env.example -f infra/local/keycloak/docker-compose.yml up -d
```

Check that the `uniattend` realm is available:

```powershell
curl.exe -I http://localhost:8080/realms/uniattend
```

Expected result:

```text
HTTP/1.1 200 OK
```

## Create A Local Student

Open the Keycloak admin console:

```text
http://localhost:8080/admin
```

Use:

```text
Username: admin
Password: admin
```

Then:

1. Select the `uniattend` realm.
2. Go to `Users`.
3. Create a user, for example `student1`.
4. Set the user email, for example `student1@students.uniattend.test`.
5. Set a non-temporary password in the `Credentials` tab.
6. Assign the `student` realm role in the `Role mapping` tab.

## Run On Android Emulator

Install dependencies from the repository root:

```powershell
npm install
```

Start the Android build:

```powershell
npm.cmd run android --workspace=apps/mobile
```

When the app opens:

1. Tap `Continue with university login`.
2. Keycloak should open in the browser.
3. Log in with the local student user.
4. After login, the app should return to the student home screen.
5. Tap the logout icon in the dashboard header.
6. Keycloak should clear the browser session and return to the login screen.

If logout does not return to the app, make sure the `uniattend-mobile` Keycloak
client has `uniattend://*` and `exp://*` configured as valid post-logout
redirect URIs. Existing local Docker volumes may need a reset before newly
imported realm settings appear.

## Validation

Run these from the repository root before opening a pull request:

```powershell
npm.cmd run typecheck --workspace=apps/mobile
npm.cmd run test:ci --workspace=apps/mobile
npm.cmd run lint --workspace=apps/mobile
```
