# MVP deployment plan (abstract)

**Owner:** Manushan with the service owners

**Planning baseline:** `origin/main` at `32082ee693c9ef0db9c5c60da38e512474d71821`, reviewed 2026-09-22

**Aim:** release one reproducible MVP build of web, Core API, face verification and Android, backed by a controlled application database, identity provider and notification delivery.

See [mvp-current-status-review.md](mvp-current-status-review.md) for the evidence and unresolved release gates. This plan is provider-neutral; choose exact hosts, domains and credentials during deployment preparation.

## 1. Freeze and assign the release

- Name a release candidate from a specific `main` commit and record the web/API/face image tags plus Android build version. Assign one release coordinator and an owner for database, identity, backend/face, web and mobile checks.
- Confirm all required PRs are merged and CI is green on that exact commit. Keep later feature work out of the candidate while the MVP is validated.
- Record the intended audience, pilot size, maintenance window and rollback decision maker.

**Exit:** one traceable candidate and named people for every release step.

## 2. Prepare the target environment and data

- Choose the hosting topology for web, API, face service and Redis. Give web and Android HTTPS endpoints; keep database, Redis and internal service calls private. Use the production web Docker target rather than the development Compose target. Configure service health, storage, capacity and observability.
- Provision application PostgreSQL and a separate Keycloak datastore if Keycloak is self-hosted. Configure the realm, roles, clients, audiences, browser redirect URIs and mobile redirect scheme. Match the issuer and JWKS values expected by the backend.
- Store secrets outside Git and Android public environment variables. Record which team member can rotate the QR HMAC secret, web session secret, database credentials, Keycloak client secret and face embedding encryption key. Do not rotate the encryption key without a data migration or recovery plan.
- Reconcile the migration ledger with the **actual target** database using read-only schema queries. Test unapplied scripts on disposable PostgreSQL, take a restorable target backup, then apply the missing scripts in filename order before starting the candidate services. Update `database/migrations/README.md` from verified results. Keep development seed data out of the release database unless an explicitly approved pilot dataset is needed.

**Exit:** configuration inventory, backup/restore proof, and verified application schema matching the candidate.

## 3. Deploy a preview candidate and validate it

- Build immutable web, Core API and face-service images from the candidate; verify the production web server starts. Confirm the face model loads and both service DB health endpoints work. Confirm Redis, issuer discovery/JWKS and browser login.
- Configure Android build-time `EXPO_PUBLIC_CORE_API_URL`, `EXPO_PUBLIC_FACE_VERIFICATION_API_URL` and the Keycloak issuer for the preview endpoints. Produce and install a signed internal Android build; confirm camera, location and notification permissions on a physical phone.
- Start push and reminder processing only after the relevant migrations and credentials are in place. Set liveness enforcement explicitly; test the enabled path, including rejected/crafted evidence.
- Exercise the roadmap's CP1–CP8 using test users and a real class/session flow: enrolment and role access; face/geofence check-in; QR batch scan and void; close/finalize and manual change; cancel; policy defaults; web/mobile/history/reports agreement; push/reminder delivery and notification taps. Check failure paths, not only successful screens.
- Capture results, logs and defects. Fix blocking defects on separate PRs, rebase the release candidate on the new `main`, and repeat affected checks.

**Exit:** a physical-device test record and signed approval from each service owner for the same candidate version.

## 4. Pilot release and observe

- Apply the verified schema and secrets to the pilot target. Deploy services with recorded image tags; publish the web endpoint; distribute the matching Android internal build. Confirm authentication and the minimal smoke flow before inviting pilot users.
- Monitor API and face-service availability, DB connectivity, face inference failures/latency, push queue and delivery failures, reminder duplicates, and attendance finalization discrepancies. Review logs without exposing tokens, credentials or biometric images.
- Keep a short pilot observation window, record incidents and decide whether to expand, pause or roll back. Publish user instructions and an escalation contact for lecturers and students.

**Exit:** agreed pilot acceptance thresholds met, or a documented rollback/repair decision.

## 5. Rollback and follow-through

- For application failure, stop new traffic or pause the rollout, redeploy the last known good web/API/face images and restore the matching Android distribution where feasible. Disable push/reminder workers if they are causing incorrect or repeated messages. Preserve logs and database evidence.
- Treat database rollback separately: these are forward migrations and some have data transformations. Restore from the tested backup only after assessing records written since release; do not blindly run a rollback script against live attendance data.
- For compromised credentials, rotate the affected secret and redeploy dependent services. For a face encryption key issue, use a reviewed key migration/recovery procedure before changing the key.
- After a stable pilot, tag the release, update the migration ledger and runbook with actual infrastructure and commands, record open issues, and plan the wider rollout.

## Go / no-go checklist

Ship only when all are evidenced on the same candidate: green CI; target migrations verified; production configuration and HTTPS correct; Keycloak login and roles; service/database health; CP1–CP8 on real services and Android; liveness enforced; notifications delivered; backup and rollback rehearsed; and owners accept the pilot risk. An unresolved item is a **no-go** until fixed or explicitly accepted by the release coordinator and affected owner.
