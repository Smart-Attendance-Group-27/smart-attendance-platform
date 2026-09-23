# First VPS release runbook

The release uses one netcup VPS. The application and Face Verification have
separate Compose projects and images. Only SSH is public during the private
stage. All commands below run on the VPS as `uniattend`, except where noted.

## Release inputs

- `/etc/uniattend/private.env`: owner `uniattend`, mode `0600`. It contains the
  full merged commit SHA, Supabase session-pooler URI, the existing face
  embedding key, and newly generated Keycloak, web and QR secrets.
- `/etc/uniattend/realm.json`: rendered Keycloak realm, mode `0600`.
- `/etc/uniattend/backup-recipient.txt`: public age recipient only. The
  corresponding private key is kept off the VPS.
- `/opt/uniattend/releases/<sha>`: exact release files.
- `/opt/uniattend/current`: symlink to the active release.

Generate `private.env` with `prepare_private_env.py`, render the realm with
`render_realm.py`, and copy both over SSH. Never place these files in Git.
The temporary `sslip.io` issuer and browser URLs are configured from the
start, although every application listener is loopback-only and ports 80/443
stay blocked until ingress is ready.

## Deploy privately

Verify the local encrypted Supabase backup and run `verify_mvp_schema.sql`
before applying any migration. The current shared database passed the schema
gate on 2026-09-24; do not replay the migrations without a new read-only audit.

```bash
deployment/ops/deploy_private.sh /opt/uniattend/current
docker compose --env-file /etc/uniattend/private.env \
  -f /opt/uniattend/current/deployment/compose.app.yml ps
docker compose --env-file /etc/uniattend/private.env \
  -f /opt/uniattend/current/deployment/compose.face.yml ps
deployment/ops/host_status.sh
```

Start a tunnel from the administrator's workstation:

```powershell
ssh -N -L 3000:127.0.0.1:3000 -L 8000:127.0.0.1:8000 `
  -L 8001:127.0.0.1:8001 -L 8080:127.0.0.1:8080 uniattend-vps
```

The private endpoints are then `http://localhost:3000`, `:8000`, `:8001`,
and `:8080`. Browser login redirects to the configured HTTPS hostname, so
complete browser authentication is tested after ingress opens. The tunnel
stage proves process health and internal service requests.

## Public HTTPS cutover

The temporary free hostnames in `public.env.example` resolve to the server IP.
They can be used for the short pilot without purchasing a domain. A university
domain can replace them later. Before opening 80/443:

1. Confirm all four DNS names resolve to the VPS and the private checks pass.
2. Confirm that `WEB_BASE_URL`, `KEYCLOAK_PUBLIC_URL`, and
   `KEYCLOAK_EXPECTED_ISSUER` in the protected environment match those DNS
   hostnames. The realm was rendered with the same web callback and logout
   URLs before its first import. Startup realm import does not overwrite an
   existing realm if URLs later change.
3. Start `compose.ingress.yml` using a protected public env file. Caddy obtains
   and renews trusted certificates, keeps their state in a named volume, and
   forwards only the specified Face health/readiness routes. `/internal/*` and
   Keycloak `/admin/*` are blocked at the public edge.
4. Open 80/tcp, 443/tcp and 443/udp in UFW after Caddy is healthy. Check
   certificate names, browser login, token validation and device flows.
5. Set the Android `EXPO_PUBLIC_*` URLs to the same HTTPS origins and build a
   new artifact. A private tunnel build cannot be used from a physical device.

Cloudflare R2 is independent of HTTPS. An R2 account and bucket credentials
are still required for the later photo storage adapter; current enrollment
continues to use approved local input files.

## Keycloak backup and recovery

The backup timer runs daily at 02:30 UTC and writes a dated encrypted
`pg_dump` under `/opt/uniattend/backups`. Copy the `.age` file off the VPS
regularly. The age private key must stay on the administrator's workstation.
The first archive should be decrypted and restored to an isolated throwaway
PostgreSQL container before student testing. Never test a restore against the
live Keycloak volume.

```bash
sudo systemctl status uniattend-keycloak-backup.timer
sudo systemctl start uniattend-keycloak-backup.service
ls -lh /opt/uniattend/backups/*.age
```

Export the Keycloak realm through the Admin API after client and user changes.
Back up both the PostgreSQL database and the realm export before identity
migration. The previous Railway Keycloak URL returned 404 on 2026-09-24;
nine Supabase users carry old Keycloak IDs, so their login migration requires
the old realm/DB backup or a controlled account reset and ID reconciliation.

## Health, rollback and shutdown

```bash
/opt/uniattend/current/deployment/ops/host_status.sh
docker logs --since 15m uniattend-app-core-api-1
docker logs --since 15m uniattend-face-face-verification-1
```

Container logs rotate at 10 MB times five files. Keep host memory below 80%,
CPU below 75% sustained, disk below 70%, and Face concurrency at one until
load testing shows room. If an image fails, set `IMAGE_TAG` to the last known
good merged SHA in `/etc/uniattend/private.env` and run `deploy_private.sh`
against that release directory. Keep the Keycloak and Redis volumes; do not
run `down -v`. A database rollback is separate from application rollback.

By day 50, export the Keycloak realm, pull final encrypted Keycloak and
Supabase backups off the VPS, record release/image digests and pilot evidence,
then stop ingress and application containers. Confirm the backups decrypt and
the netcup cancellation date. Remove the VPS only after the owner confirms
that student records and photos have been retained or deleted as agreed.
