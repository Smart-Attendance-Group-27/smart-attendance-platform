# Local development setup for teammates

The production pilot is a shared test environment. Ordinary feature work
should use a separate local database and local credentials. Do not copy
Manushan's ignored root `.env` or the VPS's `/etc/uniattend/private.env` to
another laptop just to run tests.

## Clone and prerequisites

Clone `Smart-Attendance-Group-27/smart-attendance-platform` with your own
GitHub account, fetch current `main`, and make a task branch. Install Docker
Desktop, Node.js/npm, Python supported by each service, and Android Studio or
platform tools for mobile work. The root `docker-compose.yml` is the **local
development** stack; `deployment/compose.*.yml` is the live VPS design.

Read the relevant service instructions:

- [Root setup](../../../README.md) for Compose and service ports.
- [Local application database](../../../infra/local/application-db/README.md)
  for an isolated PostgreSQL 16 database and seed.
- [Core backend](../../../services/core-backend/README.md) and
  [geofence demo](../../../docs/geofence-validation-demo.md) for API and
  manual attendance work.
- [Mobile](../../../apps/mobile/README.md) for Expo, emulator/phone networking,
  and OIDC configuration.
- Web code is in `apps/web`; its default generated README is less current than
  the root Compose configuration and deployment runbook.

The root README contains an **old Railway Keycloak issuer example**. That
instance is unreachable and is not the live pilot issuer. Use the present
`auth.152-53-33-198.sslip.io` issuer for authorized integration tests, or
start the local Keycloak fallback described in the mobile/geofence guides.
The issuer in a token must exactly match Core's configured expected issuer.

## Isolated database and environment

1. Copy `infra/local/application-db/.env.example` to its ignored `.env` and
   set a new local-only `APP_DB_PASSWORD`.
2. From the repository root, run
   `docker compose --env-file infra/local/application-db/.env -f infra/local/application-db/docker-compose.yml up -d`.
   It initializes the schema, migrations, and demo seed only on a new empty
   local volume. This is separate from Supabase and Keycloak PostgreSQL.
3. Copy root `.env.example` to a **new local** ignored `.env` and fill the
   needed app, Keycloak, QR, and face settings. Point Core and Face to the
   local application DB; leave production Supabase URIs out of this file.
   Core's `CORE_DB_URI` takes precedence over individual `CORE_DB_*` fields.
   For a backend process on the host, the local database uses `localhost:5434`;
   a backend inside Docker needs a host address reachable from the container.
4. Select local Keycloak or a specifically approved shared pilot auth test.
   Do not mix a local Keycloak issuer with production issuer/JWKS values.
   `docker compose --profile local-keycloak up --build` includes the root
   Compose Keycloak fallback when the local env is configured. The mobile
   guide also documents a standalone local Keycloak Compose project.
5. Check `docker compose config`, `docker compose ps`, Core `/health/db`,
   and Face `/health/db` before attempting attendance flows. Expo runs outside
   Docker on an emulator or phone. Use `apps/mobile/.env.example` for public
   endpoint names; never put passwords or client secrets in `EXPO_PUBLIC_*`.

Stopping the root Compose stack with `docker compose down` preserves its
volumes. `down -v` deletes **local** volumes; it must never be applied to the
VPS release projects. Do not replay migrations against live Supabase merely
because they are listed in a local setup guide.

## Development and PR checks

Run the tests relevant to the changed service, then follow
`.github/pull_request_template.md`. The repository CI runs backend, face,
web, mobile, and production-container validation on PRs. On `main`, Deployment
CI publishes commit-tagged private GHCR images. A successful PR build does
not release containers to the VPS. The deployment operator records the exact
merged SHA, performs the release, and repeats public and internal smoke tests.
