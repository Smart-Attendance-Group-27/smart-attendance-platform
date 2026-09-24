# Current MVP deployment

**Observed:** 2026-09-24 07:10 UTC. Recheck before a release or data change.

## Runtime and release identity

| Item | Current state |
| --- | --- |
| Owner and lifetime | Manushan; netcup VPS 1000 G12.5 for a roughly two-month university pilot |
| Host | Debian 13 x86_64 at `152.53.33.198`; 4 vCPU, 7.8 GiB RAM, 125 GB root disk, 2 GiB swap |
| Running source | `/opt/uniattend/current` points to `/opt/uniattend/releases/cf72fa47f529674e4510586e12e5f4d0a6540ebf` |
| Repository `main` | `7f6790101864179534422b95ef08e5542d800958` at this snapshot; includes PR #93's mobile liveness feedback but is not the running release |
| Pending documentation and fix | [PR #96](https://github.com/Smart-Attendance-Group-27/smart-attendance-platform/pull/96) records physical pilot evidence; [PR #97](https://github.com/Smart-Attendance-Group-27/smart-attendance-platform/pull/97) fixes admin academic options and carries this handoff. Check their current review and CI status before merging. |
| Images | Web, Core, Face, and Keycloak were built on the VPS from the exact running SHA. Main-branch CI also publishes private GHCR images tagged by commit SHA. Do not infer that a new GHCR image is deployed. |

At the snapshot, Web, Core, Keycloak, Keycloak PostgreSQL, Redis, Face
Verification, and Caddy were running; all six application containers with
health checks were healthy. Host memory used was about 2.5 GiB and root disk
usage 14%. These are point-in-time readings, not load-test results.

## Architecture and URLs

| Public HTTPS name | Purpose |
| --- | --- |
| <https://app.152-53-33-198.sslip.io/login> | Next.js web and server-side authentication |
| <https://api.152-53-33-198.sslip.io/health/db> | Core API database health |
| <https://auth.152-53-33-198.sslip.io/realms/uniattend/.well-known/openid-configuration> | Keycloak OIDC issuer |
| <https://face.152-53-33-198.sslip.io/health/db> | Face service database health |

The `sslip.io` names resolve to the VPS and Caddy serves trusted TLS. A
purchased domain and Cloudflare DNS are not configured. Caddy exposes only
approved Face health/readiness paths, returns 404 for public Core and Face
`/internal/*`, and blocks public Keycloak `/admin/*`. SSH and HTTPS ingress
are public; application ports 3000, 8000, 8001, and 8080 are bound to VPS
loopback. Keycloak PostgreSQL and Redis are private Docker services.

The application and Face service have separate Compose projects and images.
They communicate on the private `uniattend-services` Docker network. Face
uses CPU InsightFace `buffalo_l`, a persistent model-cache volume, one Uvicorn
worker, one concurrent inference, and a 2 GiB container memory limit. It can
be moved to another host later, but no second VPS or load balancer exists now.

Core and Face use the existing Supabase PostgreSQL database in Seoul through
TLS and small session-pooler connections. Keycloak has its own PostgreSQL
volume on the VPS. Redis is local to the VPS. The protected deployment
configuration is `/etc/uniattend/private.env` (mode `0600`); the protected
realm file is `/etc/uniattend/realm.json`. Never commit or print them.

## What has been observed

- The four public URLs above returned HTTPS 200 with certificate validation
  from the owner workstation on 2026-09-24. The hourly GitHub uptime workflow
  checks the same origins.
- Browser administrator and lecturer logins, student OIDC authorization code
  with PKCE, Core token validation, Supabase reads, Redis, Face model startup,
  blank-image inference, and intentional container restart were tested during
  deployment. The physical Android pilot APK also logged in mock students.
- The first `PILOT101` non-face attendance attempt had a low-accuracy retry.
  The next geofence decision passed. Live student state then showed an initial
  check-in, **dynamic QR** progress **1/1 required batch passed**, and final
  **present** after the session closed. A second `PILOT101` session was cancelled. This
  proves the non-face attendance outcome; Manushan confirmed that the
  successful attempt was on his physical Android phone at the configured
  test location. See the pilot guide for how to repeat it.
- Manushan reports manually checking static and dynamic QR. A read-only live
  database check confirms one accepted dynamic scan in the closed pilot
  session. Static QR batches are present, but no accepted static scan is
  recorded. Keep the reported static test distinct from the verified dynamic
  attendance result until its outcome is documented.
- The mock lecturers' 20 historical MOCK401–403 test sessions were removed
  after an encrypted Supabase backup. The original mock courses remained.
  `PILOT101` has one lecturer, one enrolled mock student, and its own test
  classroom at coordinates supplied privately by Manushan. Exact coordinates
  are not in this handoff.

## Current limits

- Core sets `PILOT_DISABLE_FACE_ATTENDANCE=true`. Face service health and
  readiness are available, but face verification is **not** an attendance
  requirement in the current pilot. Merged mobile liveness feedback in `main`
  does not change this deployed guard.
- The running Core admin academic-options endpoint returns HTTP 500 because
  it filters lecturer and student profiles by a nonexistent `status` column.
  PR #97 changes both filters to `profile_status`; the fix is not live until
  that PR is merged and a new release is deployed. The prepared lecturer and
  student attendance paths are usable without this admin selector.
- Cloudflare R2 has no account or bucket yet. The reference-photo R2
  enrollment adapter is separate future product work. The current enrollment
  CLI accepts approved local files; do not claim that R2 photos are active in
  this deployment.
- The arm64 pilot APK is debug-signed for internal testing and held outside
  Git on the owner's workstation. EAS hosted access to the existing Expo
  project was unavailable at initial deployment. A domain change requires a
  new mobile build with matching OIDC/API URLs.

## Recovery and monitoring

The Keycloak database backup timer runs daily at 02:30 UTC. It creates
encrypted `.age` dumps on the VPS with 30-day local retention. The owner's
Windows task pulls and checksum-verifies encrypted dumps at 08:15
Asia/Colombo and on logon. An isolated Keycloak database restore and realm
export verification were performed. The age private key stays off the VPS.
An encrypted full Supabase archive was verified immediately before and after
the mock-session reset and pilot setup on 2026-09-24. Recovery artifacts are
in the owner's protected `C:\Users\LOQ\.uniattend-backups` directory.
Docker JSON logs rotate at 10 MB across five files per container. Avoid raw
photos, embeddings, access tokens, and secrets in logs.

Operational commands for an authorized VPS operator:

```bash
readlink -f /opt/uniattend/current
/opt/uniattend/current/deployment/ops/host_status.sh
sudo systemctl status uniattend-keycloak-backup.timer
docker logs --since 15m uniattend-app-core-api-1
```

See [the release runbook](../../../deployment/first-vps-runbook.md) for
deployment, restore, rollback, and shutdown procedures. Never run
`docker compose down -v` on this VPS.
