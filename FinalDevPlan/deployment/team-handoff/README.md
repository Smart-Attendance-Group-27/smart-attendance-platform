# Deployment team handoff

**Owner:** Manushan

**Snapshot:** 2026-09-24 07:10 UTC

**Audience:** teammates and their coding agents working on the two-month MVP pilot

Read these files in order:

1. [Current deployment](current-deployment.md) — what is running, where it
   runs, what has been tested, and what is still outside the pilot.
2. [Next actions](next-actions.md) — work order, owners, checks, and release
   procedure.
3. [Access and credentials](access-and-credentials.md) — what Manushan should
   grant to each collaborator and what must stay out of Git and agent prompts.
4. [Local developer setup](developer-setup.md) — isolated database, current
   authentication choices, service guides, and PR checks.

The live server is **not** running the latest `main`: its application release
is `cf72fa47f529674e4510586e12e5f4d0a6540ebf`. Always compare the live
release symlink, current `main`, and open PRs before acting. This handoff is a
dated snapshot; recheck live state rather than treating it as a permanent
configuration specification.

## Start here for an AI-assisted task

Give the agent the repository and this directory, the exact assigned task,
and the relevant PR or issue. Ask it to read the current code and live-status
checks before editing. The task brief should include these boundaries:

- Use a branch from current `main`; keep each reviewed change in its own PR.
- Distinguish deployed SHA from source SHA. A merge does not deploy the VPS.
- Do not rerun database migrations or delete shared data from a fresh clone.
- Preserve `PILOT_DISABLE_FACE_ATTENDANCE=true` until the separate face and
  liveness acceptance work is complete.
- Use the existing protected environment on the VPS for authorized operations.
  Keep passwords, private keys, student photos, and embeddings out of Git,
  issue bodies, PR comments, agent prompts, and terminal output.
- Run relevant tests and CI, then record the deployed SHA and smoke evidence.

## Existing detailed references

- [Deployment report](../first-vps-deployment-report.md) and
  [release runbook](../../../deployment/first-vps-runbook.md).
- [Pilot attendance guide](../home-attendance-pilot.md).
- [Approved deployment phases](../phases.md).
- [Production Compose projects](../../../deployment/compose.app.yml),
  [Face Compose](../../../deployment/compose.face.yml), and
  [Caddy ingress](../../../deployment/compose.ingress.yml).

Some earlier documents describe their own earlier date. The current-state
file in this directory records later live observations, including the new
`PILOT101` attendance data.

## Repository map

| Area | Location |
| --- | --- |
| Web and lecturer/admin pages | `apps/web` |
| Android app and device configuration | `apps/mobile` |
| Core API, sessions, geofence, QR, and identity links | `services/core-backend` |
| Face model, enrollment, and readiness | `services/face-verification` |
| Database schema, seed, and ordered migrations | `database` |
| VPS Compose, Caddy, configuration templates, and ops scripts | `deployment` |
| Test, image-publishing, and uptime CI | `.github/workflows` |
