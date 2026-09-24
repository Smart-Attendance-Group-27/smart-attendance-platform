# First VPS deployment report

**Owner:** Manushan

**Date:** 2026-09-24 (Asia/Colombo)

**Server:** netcup VPS 1000 G12.5, `152.53.33.198`

**Release branches:** `deployment/first-vps-release`, then
`deployment/first-vps-followup`

**Initial PR:** [#91](https://github.com/Smart-Attendance-Group-27/smart-attendance-platform/pull/91),
merged as `575509055556a1b19a088c126b96746dea6e0e57`

## Current status

The pilot stack is live over trusted HTTPS on temporary `sslip.io` names. Web,
Core, Keycloak, Redis, Keycloak PostgreSQL, Face Verification, and Caddy are
healthy. Face Verification is a separate Compose project and container, with
one inference worker and a persistent model-cache volume. The current VPS
images were built from staging SHA
`9ccd433ffad45061d05ba45eef9b6190e07ece67`. PR #91 was merged while
review fixes were still being prepared. Those fixes are in a follow-up branch;
the final immutable GHCR release and redeployment from its **merged main SHA**
remain pending.

| Service | Pilot URL | Check |
| --- | --- | --- |
| Web | <https://app.152-53-33-198.sslip.io/login> | HTTPS 200; administrator and lecturer browser logins passed |
| Core | <https://api.152-53-33-198.sslip.io/health/db> | HTTPS 200; student bearer token accepted by `/api/v1/me` |
| Keycloak | <https://auth.152-53-33-198.sslip.io/realms/uniattend/> | HTTPS discovery 200; mobile authorization code with PKCE passed |
| Face | <https://face.152-53-33-198.sslip.io/health/db> | HTTPS 200; blank-image live inference returned `no_face` |

Core and Face `/internal/*`, Keycloak `/admin/*`, and public Face attendance
routes return 404 at the proxy. Database, Redis, and service management ports
are not publicly bound. SSH, 80, and 443 are the open inbound ports.

## Phase evidence

| Phase | Outcome |
| --- | --- |
| 1. Baseline | Started from current main; isolated release branch and worktree; CI suites passed. |
| 2. Runtime | Separate application and Face Compose projects, private shared network, health checks, resource limits. |
| 3. Configuration | Protected `/etc/uniattend/private.env` and realm file; reused the existing face embedding key; generated new VPS secrets. |
| 4. Images | Four production images build in CI and on the VPS. GHCR publication is configured for merged main commits and remains pending merge. |
| 5. Data | Supabase TLS and schema gate passed. No unnecessary migrations replayed. Prechange and postchange encrypted Supabase backups verified. Production Keycloak DB and realm initialized; mock identities remapped. |
| 6. Private deployment | Services started in dependency order; tunnel-only health and internal routing passed before public ingress opened. |
| 7. Validation | Browser admin/lecturer login, student mobile PKCE and Core identity, Face model startup and blank-image inference, container restart, memory, disk, and log checks passed. The test student's previous readiness record was restored after the blank-image check. A local Android APK was built and inspected, but no physical device was available for installation. |
| 8. SSH tunnel | Windows workstation tunnel to Web, Core, Face, and Keycloak tested. |
| 9. HTTPS | Temporary `sslip.io` DNS plus Caddy certificates work for all four hostnames; public route restrictions verified. Mobile configuration and a locally built Android APK point to these HTTPS origins. A purchased domain can be cut over later. |
| 10. Recovery/monitoring | Daily encrypted Keycloak backup timer enabled with a 30-day local retention window; encrypted database backup restored into an isolated container; encrypted realm export decrypted and checked off-host. Host checks and scheduled HTTPS uptime workflow added. |
| 11. Release | PR #91 was merged. A follow-up PR carries the Android issuer fix and deployment review fixes. GHCR publication and redeployment from the final merged main SHA are pending. |

At the last check, the host used 2.3 GiB of 7.8 GiB RAM and 13 GiB of 125 GiB
disk. Face used approximately 714 MiB of its 2 GiB limit, Keycloak 559 MiB
of 1.75 GiB, and Web 122 MiB of 768 MiB. The Face model cache occupies
approximately 601 MiB. Europe-to-Seoul new pooled database queries measured
about 1.7 seconds; this is acceptable for a small functional pilot but must
be observed during concurrent attendance testing.

## Recovery artifacts

The administrator's protected workstation directory is
`C:\Users\LOQ\.uniattend-backups`. It contains encrypted Supabase backups
before and after identity remapping, the encrypted Keycloak backup, encrypted
realm export, and the private recovery keys. The Keycloak backup was actually
restored to a separate PostgreSQL container with no network. The realm export
was decrypted off-host and its clients and users verified. The VPS retains
only the age **public recipient**, not the private key. The daily Keycloak
backup is still local to the VPS until each new archive is copied off-host.
The retention job deletes local Keycloak database dumps older than 30 days
after a successful replacement; the off-host copy must be verified before
then.

## Android pilot artifact

A local arm64-v8a Android APK was built from commit
`5f923545d8b010e16961a842b89f5a1c2d6ec567` and inspected. The JS bundle
contains the HTTPS app API, Face, and Keycloak URLs, and no old Railway URL.
The APK is debug-signed for internal pilot installation only; it has not
been installed on a physical device because none was connected. It is held
outside the repository at
`C:\Users\LOQ\.uniattend-artifacts\uniattend-pilot-arm64-5f923545d.apk`.
SHA-256:
`FBFF880D41000BC2DC51EEF74D9A3A71BD5836E4789009A3A2A1A01D05DF6103`.

## Identity migration

The old Railway Keycloak is unreachable. Seven previously linked, role-bearing
mock users were recreated in the new Keycloak with new random passwords and
their Supabase subject links updated in one database transaction. Two extra
local mock users had historical profiles, sessions, audit logs, or
notifications. Their Keycloak links were removed and their accounts marked
inactive; their records were retained. Seed users that were never linked to
the old Keycloak were not given new logins.

Credentials are stored only in the protected workstation file
`C:\Users\LOQ\.uniattend-backups\pilot-logins.txt` (user and SYSTEM access).
The VPS credential copy was removed. Passwords are not in Git or this report.
Change them after handoff.

| Role | Login email |
| --- | --- |
| Administrator | `admin@uniattend.test` |
| Administrator | `admin01@lectuere.uniattend.test` |
| Lecturer | `lecutere01@lectuere.uniattend.test` |
| Lecturer | `lecutere02@lectuere.uniattend.test` |
| Student | `230701a@student.uniattend.test` |
| Student | `230736r@student.uniattend.test` |
| Student | `230737r@student.uniattend.test` |

## Remaining acceptance work

1. Review and merge the follow-up deployment PR, confirm GHCR images publish,
   and redeploy the exact merged main SHA. Run smoke tests once more.
2. Install the local pilot APK on an Android physical device and run a
   supervised attendance pilot. Expo EAS access for `manushanhasanka` is
   unavailable on the `techumeda55` project, so a hosted preview build
   remains unavailable. Attendance face enforcement remains disabled while
   liveness is unfinished; existing face-required sessions cannot complete
   through the pilot API and must be replaced with non-face pilot sessions.
3. Create a Cloudflare account and private R2 bucket when approved reference
   photos are ready. The enrollment storage adapter is a separate product PR;
   R2 is not active in this release.
4. Arrange a recurring off-host copy of new Keycloak backup files and exercise
   the two-month shutdown/export plan before cancelling the VPS.
