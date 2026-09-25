# Current MVP deployment

**Observed:** 2026-09-25 after the PR #101 release. Recheck before a
release or data change.

## Runtime and release identity

| Item | Current state |
| --- | --- |
| Owner and lifetime | Manushan; netcup VPS 1000 G12.5 for a roughly two-month university pilot |
| Host | Debian 13 x86_64 at `152.53.33.198`; 4 vCPU, 7.8 GiB RAM, 125 GB root disk, 2 GiB swap |
| Running source | `/opt/uniattend/current` points to `/opt/uniattend/releases/0191fd3fe534569ffc828bf38d9684f630b63e37` |
| Repository `main` | `0191fd3fe534569ffc828bf38d9684f630b63e37` at this snapshot |
| Merged changes | [PR #101](https://github.com/Smart-Attendance-Group-27/smart-attendance-platform/pull/101) adds post-deployment fixes and correction requests. PR #100 enabled face attendance. |
| Images | Web, Core, Face, and Keycloak were built on the VPS from the exact running SHA. Main-branch CI passed and published private GHCR images with the same SHA. The VPS runs its locally built images. |

At the snapshot, Web, Core, Keycloak, Keycloak PostgreSQL, Redis, Face
Verification, and Caddy were running; all six application containers with
health checks were healthy. Host memory used was about 2.5 GiB and root disk
usage 14%. Face used about 703 MiB of its 2 GiB limit. These are point-in-time
readings, not load-test results. The prior
`5cb1ca71369184cd85776750b14084f779887a50` release remains available for
application rollback.

Locally built release image IDs:

| Service | Image ID |
| --- | --- |
| Web | `sha256:cd091cfff08b92c75967fde7d4248de12eee7d2672686708e2758dbd8a076ed9` |
| Core | `sha256:046fb083465a8265d0f5ff2926ac3e6fffd606fa51e1a9ac1307bf8bbaa0aeeb` |
| Face | `sha256:522731dc1f78e7a1e4c596a6aa7b9ea4efc22074d6e1c94d2bb182f36cd43386` |
| Keycloak | `sha256:22ea94fe18416771527bc748381b323b222b1620bbddfd0ddf3eb6f40362afb6` |

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
  from the owner workstation after the `0191fd3` release on 2026-09-25.
  Public Core and Face `/internal/*` and Keycloak `/admin/*` returned 404.
  The hourly GitHub uptime workflow checks the public origins.
- A pilot administrator completed Keycloak authorization code login with
  PKCE after release. Core accepted the token, and
  `GET /api/v1/administrators/me/academic-options` returned HTTP 200 with
  classroom, department, lecturer, semester, and student option groups.
  A read-only database check found the active `PILOT101` course and its
  offering. No migration or seed was run for this release.
- PR #100's exact merged SHA was built on the VPS and deployed in dependency
  order. Core reports `PILOT_DISABLE_FACE_ATTENDANCE=false`; its Face URL is
  the private Docker service. Face loaded `buffalo_l` on CPU with one
  concurrent inference and fresh liveness evidence limited to 120 seconds.
  All containers became healthy before the release symlink changed.
- A read-only post-release database audit found one active verification
  configuration at threshold `0.50000` and three encrypted, generated,
  readiness-passed 512-dimensional profiles. The enrolled `PILOT101` student
  has a ready `buffalo_l` version `1` profile. No embedding value, key, image,
  or token was printed during the audit.
- PR #101's correction-request migration was applied by itself after a fresh,
  verified encrypted Supabase backup. The new empty table has all 13 columns,
  9 constraints, and 3 indexes. Both lecturer and administrator endpoints are
  live and require authentication. Production API docs and OpenAPI routes
  return 404 as intended. No seed or unrelated migration was run.
- An interrupted release attempt stopped after Keycloak recreation. The first
  managed retry hit a Git ownership check and restored the previous image
  tag and Keycloak container. The corrected managed job completed with all
  application health checks passing before the `current` link changed.
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
- Manushan confirmed he tested dynamic QR only. A read-only live database
  check confirms one accepted dynamic scan in the closed pilot session.
  Static QR batches are present, but no accepted static scan is recorded;
  static QR remains untested in the physical attendance pilot.
- The mock lecturers' 20 historical MOCK401–403 test sessions were removed
  after an encrypted Supabase backup. The original mock courses remained.
  `PILOT101` has one lecturer, one enrolled mock student, and its own test
  classroom at coordinates supplied privately by Manushan. Exact coordinates
  are not in this handoff.

## Current limits

- Core sets `PILOT_DISABLE_FACE_ATTENDANCE=false`, so any eligible course can
  create a face-required attendance session. Deployment and stored-profile
  readiness have passed, but a real physical-device face match, initial
  check-in, and final attendance result have not yet been recorded for this
  release. The current client-generated liveness evidence is validated for
  supported challenges, success, and age, but it is not cryptographically
  bound to a server-issued challenge.
- Cloudflare R2 has no account or bucket yet. The reference-photo R2
  enrollment adapter is separate future product work. The current enrollment
  CLI accepts approved local files; do not claim that R2 photos are active in
  this deployment.
- An EAS preview APK is available from build
  `75470b13-cbc9-43ef-94bb-758c823a370c`; its verified local copy and checksum
  are held outside Git on the owner's workstation. It uses a different signer
  from the older debug APK, so Android must uninstall the older build before
  installing it. A domain change requires a new mobile build with matching
  OIDC/API URLs.

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
