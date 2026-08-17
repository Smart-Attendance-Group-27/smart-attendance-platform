# Local Keycloak Setup

This folder contains the local development setup for UniAttend authentication.

Keycloak is the authentication server. It owns login, password handling, roles,
sessions, and tokens. The mobile app should open Keycloak for login instead of
collecting a student's university password directly.

## What Runs Locally

The Docker Compose setup starts two containers:

- `keycloak-db`: PostgreSQL database used only by local Keycloak.
- `keycloak`: Keycloak server for local development.

The database data is stored in the Docker volume named
`uniattend-local-keycloak_keycloak_db_data`.

## Local URLs And Credentials

| Item | Default |
| --- | --- |
| Keycloak URL | `http://localhost:8080` |
| Admin console | `http://localhost:8080/admin` |
| Admin username | `admin` |
| Admin password | `admin` |
| PostgreSQL host port | `5433` |

These values are for local development only.

## Imported Realm

Keycloak imports the local realm file from:

```text
infra/local/keycloak/realm/uniattend-realm.json
```

The imported realm is named `uniattend`.

It creates:

- `student`, `lecturer`, and `administrator` realm roles.
- `uniattend-mobile`, a public OpenID Connect mobile client.
- `uniattend-web`, a confidential OpenID Connect client for the Lecturer/Administrator
  web dashboard (`apps/web`). PKCE-enabled like the mobile client, but confidential
  (client secret) since it runs server-side, unlike the mobile app.
- PKCE with `S256` for both the mobile and web clients.
- Browser-based login flow support.
- Post-logout redirects back to the mobile app / web dashboard.
- Direct password grant disabled, so neither client collects and submits
  passwords directly — both redirect to Keycloak's own login page.

If Keycloak was already started before this realm file was added, reset the local
database once so Keycloak can import the realm on a fresh start.

> **Note on an already-running local Keycloak**: `--import-realm` only imports on a
> *fresh* database — if your local Keycloak container has been running since before
> the `uniattend-web` client (or any other realm change) was added to this file, it
> won't appear automatically. Either reset local data (see below) or add it live with
> `kcadm.sh create clients ...`, matching the "Create Test Lecturer/Administrator
> Users" section's style, and keep this file in sync as the source of truth for
> anyone starting from a fresh database.

## Start Keycloak

Run this from the repository root:

```powershell
docker compose --env-file infra/local/keycloak/.env.example -f infra/local/keycloak/docker-compose.yml up -d
```

What this does:

- Downloads the PostgreSQL and Keycloak images if needed.
- Starts the local PostgreSQL database.
- Starts Keycloak after the database is healthy.
- Imports the `uniattend` realm when starting with a fresh local database.
- Opens Keycloak on `http://localhost:8080`.

## Check Container Status

```powershell
docker compose --env-file infra/local/keycloak/.env.example -f infra/local/keycloak/docker-compose.yml ps
```

Both services should show as running.

## Open The Admin Console

Open this URL in your browser:

```text
http://localhost:8080/admin
```

Use:

```text
Username: admin
Password: admin
```

To view the imported UniAttend realm, open the realm selector in the admin
console and choose `uniattend`.

## Verify The Imported Realm

Run this after Keycloak has finished starting:

```powershell
curl.exe -I http://localhost:8080/realms/uniattend
```

Expected result:

```text
HTTP/1.1 200 OK
```

If this returns `404 Not Found`, Keycloak is running but the `uniattend` realm
has not been imported into the current local database. Reset local data once and
start Keycloak again.

## Verify Roles And Mobile Client

Log in to the local Keycloak admin CLI:

```powershell
docker exec uniattend-keycloak /opt/keycloak/bin/kcadm.sh config credentials --server http://localhost:8080 --realm master --user admin --password admin
```

Check the imported realm roles:

```powershell
docker exec uniattend-keycloak /opt/keycloak/bin/kcadm.sh get roles -r uniattend
```

Expected UniAttend roles:

```text
student
lecturer
administrator
```

Check the imported mobile client:

```powershell
docker exec uniattend-keycloak /opt/keycloak/bin/kcadm.sh get clients -r uniattend -q clientId=uniattend-mobile
```

Expected mobile client settings:

```text
clientId: uniattend-mobile
publicClient: true
standardFlowEnabled: true
implicitFlowEnabled: false
directAccessGrantsEnabled: false
pkce.code.challenge.method: S256
redirectUris: uniattend://*, exp://*
post.logout.redirect.uris: uniattend://*, exp://*
```

## Verify The Web Dashboard Client

```powershell
docker exec uniattend-keycloak /opt/keycloak/bin/kcadm.sh get clients -r uniattend -q clientId=uniattend-web
```

Expected web client settings:

```text
clientId: uniattend-web
publicClient: false
standardFlowEnabled: true
implicitFlowEnabled: false
directAccessGrantsEnabled: false
serviceAccountsEnabled: false
pkce.code.challenge.method: S256
redirectUris: http://localhost:3000/api/auth/callback
post.logout.redirect.uris: http://localhost:3000/login
```

It should also carry a `uniattend-api-audience` protocol mapper (same as the mobile
client) — `apps/web`'s access tokens need the `uniattend-api` audience for
`services/core-backend` to accept them:

```powershell
docker exec uniattend-keycloak /opt/keycloak/bin/kcadm.sh get clients -r uniattend -q clientId=uniattend-web --fields id
# use the returned id below
docker exec uniattend-keycloak /opt/keycloak/bin/kcadm.sh get clients/<id>/protocol-mappers/models -r uniattend
```

The client secret for local development is `uniattend-web-dev-secret-change-me`
(matches `apps/web/.env.example`'s `KEYCLOAK_CLIENT_SECRET`) — this is a dev-only
placeholder, same tier as the admin password above. A real deployment must generate
its own secret in the Keycloak admin console and set it only via a non-committed
environment variable.

## Create Test Lecturer/Administrator Users

Neither the `lecturer` nor `administrator` role has a seed user in the realm file
(same convention as `student` — see `docs/backend/integration-and-manual-testing.md`
for the equivalent student setup). Create one of each locally:

```powershell
docker exec uniattend-keycloak /opt/keycloak/bin/kcadm.sh create users -r uniattend `
  -s username=lecturer1 -s email=lecturer1@lecturers.uniattend.test -s emailVerified=true `
  -s enabled=true -s firstName=Dulani -s lastName=Meedeniya

docker exec uniattend-keycloak /opt/keycloak/bin/kcadm.sh add-roles -r uniattend --uusername lecturer1 --rolename lecturer
docker exec uniattend-keycloak /opt/keycloak/bin/kcadm.sh set-password -r uniattend --username lecturer1 --new-password 'Lecturer1Pass!' --temporary=false

docker exec uniattend-keycloak /opt/keycloak/bin/kcadm.sh create users -r uniattend `
  -s username=admin1 -s email=admin1@administrators.uniattend.test -s emailVerified=true `
  -s enabled=true -s firstName=Sunimal -s lastName=Rathnayake

docker exec uniattend-keycloak /opt/keycloak/bin/kcadm.sh add-roles -r uniattend --uusername admin1 --rolename administrator
docker exec uniattend-keycloak /opt/keycloak/bin/kcadm.sh set-password -r uniattend --username admin1 --new-password 'Admin1Pass!' --temporary=false
```

Sign in at `http://localhost:3000/login` with either account to reach the real
(non-mock) lecturer or administrator dashboard.

## Stop Keycloak

```powershell
docker compose --env-file infra/local/keycloak/.env.example -f infra/local/keycloak/docker-compose.yml down
```

This stops the containers but keeps the PostgreSQL Docker volume, so local
Keycloak data is preserved.

## Reset Local Keycloak Data

Use this only when you want a fresh local Keycloak database:

```powershell
docker compose --env-file infra/local/keycloak/.env.example -f infra/local/keycloak/docker-compose.yml down -v
```

The `-v` flag deletes the Docker volume and removes local Keycloak data.

## Validate The Compose File

```powershell
docker compose --env-file infra/local/keycloak/.env.example -f infra/local/keycloak/docker-compose.yml config
```

This checks that Docker Compose can read the configuration.

## Production Note

This setup is not production configuration. A deployed Keycloak environment must
use real secrets, HTTPS, a production PostgreSQL database, backups, and restricted
network access.
