# Next actions for the deployment team

Use this order. Assign a named owner and record the PR, release SHA, and
evidence for each change. Do not apply the seed or the full migration set to
the existing Supabase database: the first release's schema gate passed, and
the pilot data is already live.

## 1. Use the merged-main release path for future changes

[PR #100](https://github.com/Smart-Attendance-Group-27/smart-attendance-platform/pull/100)
merged. Release `5cb1ca71369184cd85776750b14084f779887a50` is live. Its
CI, service health, public HTTPS, private-route, Face model, runtime settings,
and stored-profile readiness checks passed. The previous
`d0152d947f18e9204252cd597fd9e49e618c00a4` release is retained for rollback.
Face attendance is enabled; physical face attendance acceptance is still due.

For the next change:

1. Create a feature or fix branch from current `main`, review it through a PR
   into `main`, and wait for the merged commit's CI. A new head commit may
   require a fresh review under stale-approval protection.
2. Release that exact merged `main` SHA, following
   [the runbook](../../../deployment/first-vps-runbook.md). The VPS currently
   builds local images from the selected SHA because private GHCR pulls need
   a separate read-package credential. Main CI also publishes commit-tagged
   images. A merge alone does not deploy the VPS.
3. Verify HTTPS health, Keycloak login, Core token, `PILOT101` visibility,
    Face health, private-route restrictions, and the changed feature. Record
    the active release SHA and image IDs, then retain the prior release for
    rollback. Use `PILOT_DISABLE_FACE_ATTENDANCE=true` as the emergency stop
    if the supervised face pilot exposes a serious failure.

Carry any later verified static QR result into the deployment evidence before
treating static QR as accepted. The admin options endpoint passed its
authenticated API check; repeat the browser course-management form flow when
that UI next changes.

## 2. Preserve and repeat the attendance pilot evidence

The live `PILOT101` records already show one closed non-face session with a
passed geofence, initial check-in, dynamic QR 1/1, and final present, plus one
cancelled session. Manushan confirmed that the successful attempt used his
physical Android phone at the private test location. This completes the
first non-face attendance acceptance check. Preserve the session ID,
outcome, and owner confirmation in the deployment report. Repeat with more
students only if the pilot scope expands or a regression needs investigation.
Keep the precise location and screenshots with private student data out of
Git. The [pilot guide](../home-attendance-pilot.md) has repeatable steps.

**Observed acceptance:** lecturer session was closed with one present; student
state has an initial check-in and final present; geofence passed after one
accuracy retry; one required dynamic QR batch passed. Static QR has not been
tested on the physical attendance path. If static acceptance is required,
repeat the student scan and verify the server record and final outcome.
Retain these facts without copying raw location samples, QR values, or
credentials into a PR.

## 3. Complete physical face-attendance acceptance

Release `5cb1ca71369184cd85776750b14084f779887a50` made the global
face-attendance switch configurable and deployed it as
`PILOT_DISABLE_FACE_ATTENDANCE=false`. The live audit found three encrypted,
generated, readiness-passed profiles, one active verification configuration,
and a ready `PILOT101` student. Follow the
[face attendance enablement guide](face-attendance-enablement.md) for the exact
flow, rollback switch, pilot limitation, and physical-device acceptance.

Do not treat session creation, a readiness record, or blank-image inference as
proof of a successful attendance match. Record a real liveness pass, biometric
match, initial check-in, and final attendance result on the physical device.

## 4. Add private reference-photo storage when an account exists

Manushan reported no Cloudflare account or R2 bucket yet. Create a private
bucket with scoped credentials and a retention rule only after that account
and ownership are settled. Implement the separate enrollment adapter PR to
read approved photos from R2; test mapping, dry-run, commit mode, and cleanup.
Keep raw live attendance images out of R2 and logs. R2 is not required for
the current geofence/QR pilot.

## 5. Operate and end the short pilot

- Check the Keycloak backup timer, off-host encrypted copy, uptime workflow,
  container health, memory, CPU, and disk weekly. The owner workstation must
  be on often enough to pull backups before the VPS's 30-day retention ends.
- Measure Europe-to-Seoul Supabase latency and single-worker Face inference
  during concurrent student testing. The current resource readings are idle
  snapshots, not scale proof. Keep face concurrency at one until tested.
- A permanent domain is optional. If added, update Caddy, Keycloak issuer and
  redirect URIs, web/Core origins, and mobile build together, then repeat
  browser and device OIDC tests.
- Before the two-month contract ends, export the realm, verify final encrypted
  Keycloak and Supabase backups off-host, decide reference-photo retention,
  and confirm the netcup cancellation date and billing stop.
