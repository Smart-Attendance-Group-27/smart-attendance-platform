# Next actions for the deployment team

Use this order. Assign a named owner and record the PR, release SHA, and
evidence for each change. Do not apply the seed or the full migration set to
the existing Supabase database: the first release's schema gate passed, and
the pilot data is already live.

## 1. Finish the current review and release chain

1. Recheck every open deployment PR against current `main`, including the EAS
   ownership change and the face-attendance enablement change. Review their
   latest commits and CI. PR #96 and PR #97 are already merged and their
   evidence is part of the current deployment history.
2. Merge approved PRs in a clear order. A new head commit may require a fresh
   review under the repository's stale-approval protection. Do not dismiss
   reviews just to clear the merge gate.
3. Release the exact resulting merged `main` SHA. The present VPS uses local
   images built from a merged SHA because private GHCR pulls require a
   separate read-package credential. Main CI still publishes commit-tagged
   images. Follow `deployment/first-vps-runbook.md` and retain the current
   release for rollback. For the face-attendance release, set
   `PILOT_DISABLE_FACE_ATTENDANCE=false` only with the enablement guide's
   prerequisites and acceptance checks.
4. Run post-release HTTPS health, Keycloak login, Core token, `PILOT101`
   course visibility, Face health, and private-route checks. Specifically
   verify `GET /api/v1/administrators/me/academic-options` is HTTP 200 with
   an administrator token after PR #97 is deployed. Record new image IDs and
   the active `/opt/uniattend/current` target. Do not change the Keycloak or
   Supabase databases merely to roll out the admin query fix.

**Acceptance:** all release containers healthy, tests and protected GitHub
checks green, the selected SHA recorded, admin options 200, and rollback path
known. A merge alone does not meet this acceptance.

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

## 3. Release and validate face attendance

The next reviewed release makes the global face-attendance switch configurable
and enables it with `PILOT_DISABLE_FACE_ATTENDANCE=false`. The live audit found
three decryptable generated profiles, one active verification configuration,
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
