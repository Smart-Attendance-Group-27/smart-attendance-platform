# UniAttend Mobile

Expo mobile application for UniAttend student attendance.

## Local Keycloak Login

The mobile app uses Keycloak for credential entry. The app must not collect and
submit a student's university password directly.

For Android emulator testing, the app points to:

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
5. Tap the logout icon in the dashboard header to clear the session.

## Validation

Run these from the repository root before opening a pull request:

```powershell
npm.cmd run typecheck --workspace=apps/mobile
npm.cmd run test:ci --workspace=apps/mobile
npm.cmd run lint --workspace=apps/mobile
```
