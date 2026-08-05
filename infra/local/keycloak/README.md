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
- PKCE with `S256` for the mobile client.
- Browser-based login flow support.
- Direct password grant disabled, so the mobile app does not collect and submit
  passwords directly.

If Keycloak was already started before this realm file was added, reset the local
database once so Keycloak can import the realm on a fresh start.

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
```

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
