# First VPS deployment report

**Owner:** Manushan

**Date:** 2026-09-24 (Asia/Colombo)

**Server:** netcup VPS 1000 G12.5, `152.53.33.198`

**Release branches:** `deployment/first-vps-release`, then
`deployment/first-vps-followup`

**Initial PR:** [#91](https://github.com/Smart-Attendance-Group-27/smart-attendance-platform/pull/91),
merged as `575509055556a1b19a088c126b96746dea6e0e57`

**Follow-up PR:** [#94](https://github.com/Smart-Attendance-Group-27/smart-attendance-platform/pull/94),
merged as `cf72fa47f529674e4510586e12e5f4d0a6540ebf`

**Active release:** `5cb1ca71369184cd85776750b14084f779887a50`

## Current status

The pilot stack is live over trusted HTTPS on temporary `sslip.io` names. Web,
Core, Keycloak, Redis, Keycloak PostgreSQL, Face Verification, and Caddy are
healthy. Face Verification is a separate Compose project and container, with
one inference worker and a persistent model-cache volume. The four VPS images
were built from the exact active merged-main commit and are tagged with its
full SHA. The same commit's four images were also published to private GHCR by
[Deployment CI](https://github.com/Smart-Attendance-Group-27/smart-attendance-platform/actions/runs/36049112895).
Manushan selected a direct VPS build for this two-month pilot, so the running
local image IDs below are the release record rather than GHCR pull digests.

| Service | Pilot URL | Check |
| --- | --- | --- |
| Web | <https://app.152-53-33-198.sslip.io/login> | HTTPS 200; administrator and lecturer browser logins passed |
| Core | <https://api.152-53-33-198.sslip.io/health/db> | HTTPS 200; post-release student bearer token accepted by `/api/v1/me` |
| Keycloak | <https://auth.152-53-33-198.sslip.io/realms/uniattend/> | HTTPS discovery 200; post-release mobile authorization code with PKCE passed |
| Face | <https://face.152-53-33-198.sslip.io/health/db> | HTTPS 200; blank-image live inference returned `no_face` |

HTTPS, database, container-health, student PKCE, and Core identity checks were
repeated after the original main-SHA deployment. At that time, the live Core
GET and POST face attendance routes returned `FACE_ATTENDANCE_NOT_ENABLED` as
configured. The later PR #100 release removed that global pilot block as
recorded below.
Role-based browser login and blank-image inference were performed on the
staging build before the final source merge. Two mock students subsequently
signed in through Keycloak on a physical Android phone. The first attendance
attempt was away from its classroom and stopped at the location-accuracy
gate. Manushan later completed a non-face `PILOT101` check-in on the physical
phone at the configured pilot location: geofence passed after one
low-accuracy retry, the required dynamic QR batch passed, and closing the session
recorded final present.

Core and Face `/internal/*`, Keycloak `/admin/*`, and public Face attendance
routes return 404 at the proxy. Database, Redis, and service management ports
are not publicly bound. SSH, 80, and 443 are the open inbound ports.

### Face-attendance release — 2026-09-25

[PR #100](https://github.com/Smart-Attendance-Group-27/smart-attendance-platform/pull/100)
merged as `5cb1ca71369184cd85776750b14084f779887a50`. Backend, Mobile,
Web, and Deployment CI passed. The exact commit was built on the VPS and
deployed with `PILOT_DISABLE_FACE_ATTENDANCE=false`; the former release
`d0152d947f18e9204252cd597fd9e49e618c00a4` remains available for rollback.

All containers became healthy before `/opt/uniattend/current` changed. Web,
Core, Face database health, and Keycloak discovery returned HTTPS 200, while
public internal routes returned 404. Face loaded `buffalo_l` on CPU and used
about 703 MiB of its 2 GiB limit. A read-only database audit confirmed three
encrypted, generated, readiness-passed 512-dimensional profiles, one active
threshold at `0.50000`, and a ready `buffalo_l` version `1` profile for the
`PILOT101` student. No database migration or seed was run.

This completes the server release and makes face-required sessions available
for all eligible courses. A supervised physical-device match, initial
check-in, safe failure, and final attendance outcome are still required before
the face attendance path is marked accepted end to end.

## Phase evidence

| Phase | Outcome |
| --- | --- |
| 1. Baseline | Started from current main; isolated release branch and worktree; CI suites passed. |
| 2. Runtime | Separate application and Face Compose projects, private shared network, health checks, resource limits. |
| 3. Configuration | Protected `/etc/uniattend/private.env` and realm file; reused the existing face embedding key; generated new VPS secrets. |
| 4. Images | Four production images built from the merged main SHA on the VPS; the main-branch CI also published all four private GHCR images successfully. |
| 5. Data | Supabase TLS and schema gate passed. No unnecessary migrations replayed. Prechange and postchange encrypted Supabase backups verified. Production Keycloak DB and realm initialized; mock identities remapped. |
| 6. Private deployment | Services started in dependency order; tunnel-only health and internal routing passed before public ingress opened. |
| 7. Validation | Browser admin/lecturer login passed in staging. Student mobile PKCE, Core identity, and the pilot face guard passed again after release. Face model startup and blank-image inference, container restart, memory, disk, and log checks passed. The test student's previous readiness record was restored after the blank-image check. A physical Android phone completed a later `PILOT101` non-face session: passed geofence, initial check-in, dynamic QR 1/1, and final present. |
| 8. SSH tunnel | Windows workstation tunnel to Web, Core, Face, and Keycloak tested. |
| 9. HTTPS | Temporary `sslip.io` DNS plus Caddy certificates work for all four hostnames; public route restrictions verified. The Android APK used these HTTPS origins for physical-device Keycloak login and live Core data. A purchased domain can be cut over later. |
| 10. Recovery/monitoring | Daily encrypted Keycloak backup timer and 30-day local retention enabled. The 08:15 workstation task succeeded; a post-release encrypted dump was copied and checksum-verified off-host. Database restore and realm export verification passed earlier. Host checks and HTTPS uptime workflow are active. |
| 11. Release | PRs #91, #94, and later #100 merged; main CI passed and published images; exact merged SHA deployed, public HTTPS and private routing checked. |

Phases 1–11 are complete for the agreed first deployment scope. Face
attendance was enabled in the later release recorded above; its supervised
physical-device acceptance remains open. A permanent domain is optional for
this pilot because the four temporary names have trusted TLS, including on
the physical phone.

At the latest post-release check, the host used 2.3 GiB of 7.8 GiB RAM and
17 GiB of 125 GiB disk. Face used approximately 703 MiB of its 2 GiB limit,
Keycloak 509 MiB of 1.75 GiB, and Web 104 MiB of 768 MiB. The Face model cache occupies
approximately 601 MiB. Europe-to-Seoul new pooled database queries measured
about 1.7 seconds; this is acceptable for a small functional pilot but must
be observed during concurrent attendance testing.

| Image | VPS image ID |
| --- | --- |
| Web | `sha256:c9845d65454774000b4406ad8e1b3caacf2272fe027bc1bf5b84bc54dc65c587` |
| Core API | `sha256:b5bd57d28be51a69ef757b9525c8238d15ae7d9ecebb4013b2fbb25427afa15d` |
| Face Verification | `sha256:595c8733dd0c5f8ba066339c06f7c45c06d55a6c3eb3ea59031eb26848fcdd5d` |
| Keycloak | `sha256:aa23c300d64bdfe4599ba169c788375e1eb8c1d1bd29260278a829af418be5f9` |

## Recovery artifacts

The administrator's protected workstation directory is
`C:\Users\LOQ\.uniattend-backups`. It contains encrypted Supabase backups
before and after identity remapping, the encrypted Keycloak backup, encrypted
realm export, and the private recovery keys. The Keycloak backup was actually
restored to a separate PostgreSQL container with no network. The realm export
was decrypted off-host and its clients and users verified. The VPS retains
only the age **public recipient**, not the private key. The administrator's
workstation has a daily 08:15 Asia/Colombo and logon scheduled task to
pull and checksum-verify new encrypted dumps. The scheduled task's test run
returned success at 08:15, and a post-release
`keycloak-2026-09-24T024942Z.dump.age` archive was copied and verified.
Check its last
result weekly, since a powered-off workstation cannot pull until it next
starts. The retention job deletes local Keycloak database dumps older than
30 days only after a successful replacement; the off-host copy must be
verified before then. A protected 0600 copy of the pre-release environment
is at `/etc/uniattend/private.env.pre-cf72fa4` for rollback.

## Android pilot artifact

A local arm64-v8a Android APK was built from commit
`5f923545d8b010e16961a842b89f5a1c2d6ec567` and inspected. The mobile
source tree has no changes between that commit and the deployed release SHA.
The JS bundle contains the HTTPS app API, Face, and Keycloak URLs, and no old
Railway URL. The APK is debug-signed for internal pilot use. It was installed
in place with `adb install -r` on a Samsung SM-A536E (Android API 36),
preserving the app's existing data. It is held outside the repository at
`C:\Users\LOQ\.uniattend-artifacts\uniattend-pilot-arm64-5f923545d.apk`.
SHA-256:
`FBFF880D41000BC2DC51EEF74D9A3A71BD5836E4789009A3A2A1A01D05DF6103`.

### Physical-device result

On 2026-09-24, `230701a@student.uniattend.test` signed in through the
phone's Keycloak browser flow and loaded its course dashboard. After sign-out,
`230737r@student.uniattend.test` signed in and loaded the MOCK401 dashboard.
The enrolled student's phone displayed a new active, geofence-required,
non-face MOCK401 test session and opened its location check-in screen.

Two location checks reached Core, and the app reported that location accuracy
was too low after each response. The app maps both `LOCATION_ACCURACY_TOO_LOW`
and `ACCURACY_UNAVAILABLE` to that message, so the specific backend reason was
not confirmed in this test.
Fine and coarse location permissions were granted on the phone. The student
was physically away from the session's LH-02 classroom area. Therefore the
test did **not** establish either a successful in-class geofence decision or
an `OUTSIDE_GEOFENCE` decision; accuracy was rejected first. The student's
attendance state had no initial check-in or final attendance. The temporary
session `87d70d08-e30f-4f2d-a8ff-459008b33a8a` was cancelled after the
test. No mock GPS location was used.

After a separate pilot classroom and `PILOT101` course were prepared at the
location Manushan supplied privately, he completed attendance on the physical
Android phone there. The live `PILOT101` session
`c15d8257-0ee9-485a-b74c-48a9cf6dfe78` required geofence and QR, with
face verification off. Its geofence records show one
`LOCATION_ACCURACY_TOO_LOW` retry followed by a passed decision. Student
state shows an initial check-in, dynamic QR progress **1/1 required batch passed**,
and final **present** after the lecturer closed the session. A second
`PILOT101` session was cancelled without attendance. Manushan confirmed the
successful check-in used his phone at the configured test location; exact
coordinates and raw readings are not in this report.

Manushan clarified that he tested dynamic QR only. A read-only live database
check confirms the accepted pilot scan used a dynamic batch. Static batches
exist, but there is no recorded accepted static scan; static QR remains
untested in the physical attendance pilot.

Before this later test, 20 historical MOCK401–403 test sessions were removed
from the two mock lecturers' dashboards after a verified encrypted Supabase
backup. A second encrypted archive of the prepared pilot state was verified.
The original mock courses remained, and historical audit logs were retained.

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

1. Face attendance is enabled. Complete the supervised `PILOT101` physical
   acceptance: create and activate a face-required session, pass geofence and
   the two client challenges, confirm biometric match and initial check-in,
   close the session, and verify final Present. Also record one safe failure.
   EAS preview build `75470b13-cbc9-43ef-94bb-758c823a370c` is available for
   sharing; it has a different signer from the older debug APK.
2. Create a Cloudflare account and private R2 bucket when approved reference
   photos are ready. The enrollment storage adapter is a separate product PR;
   R2 is not active in this release.
3. Check the workstation backup task weekly and exercise the two-month
   shutdown/export plan before cancelling the VPS.
