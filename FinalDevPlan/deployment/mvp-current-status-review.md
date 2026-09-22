# MVP deployment readiness review

**Reviewed:** 2026-09-22

**Reviewer:** Manushan deployment branch review

**Source:** `origin/main` at `32082ee693c9ef0db9c5c60da38e512474d71821`

**Decision:** Development has converged on `main`; the MVP is **not yet cleared for deployment**. The release gates below need evidence from a deployed preview environment and the target database.

## What is present on `main`

| Area | Current repository evidence | Readiness assessment |
| --- | --- | --- |
| Integration | PRs #63, #70, #71, #73–#82 are merged; `gh pr list --state open` returned no open PRs at review time. The QR evidence, notification producer and attendance policy providers are bound in `services/core-backend/modules/contracts/providers.py`. | Core development integration is present. Merged code alone does not prove a deployed flow. |
| CI | Web, Backend and Mobile CI passed on the reviewed `main` SHA. Web runs typecheck, lint, tests and a production build; Backend runs both Python test suites; Mobile runs typecheck, lint and tests. | Good source-level baseline. CI does not build an Android release artifact, run database migrations, exercise external services, or test a complete device flow. |
| Services | Dockerfiles exist for web, core API and face verification. The web Dockerfile has a production target. The core and face services expose `/health` and `/health/db`. Redis and Keycloak are represented in the local Compose stack. | Deployable components exist, but target-environment configuration, images, networking and service-level smoke tests remain to be established. |
| Mobile | Expo EAS profiles and Android package metadata exist; the app implements attendance, face/QR and notification flows. | No verified release APK/AAB or physical Android acceptance result is recorded by this review. |
| Database | Baseline and forward SQL migrations exist. `database/migrations/README.md` records live schema checks dated 2026-09-22 for the earlier migrations and the attendance policy migration. | The same log marks four later migrations unapplied. Recheck the target database before release because the log can change after this review. |

## Release gates and current gaps

1. **Reconcile and apply outstanding application migrations.** The migration log marks `20260921_02_notification_indexes_and_types`, `20260922_01_session_check_in_explicit_fields`, `20260922_02_push_delivery_retry_schedule` and `20260922_03_upcoming_class_reminder_idempotency` as **not applied** to shared Supabase on 2026-09-22. The cancellation notification type is missing, and the README documents lost cancellation notifications as a current consequence. The session timing code reads the new explicit-field columns, making that migration a prerequisite for the merged code. Verify each migration on a disposable database, then back up and apply missing migrations to the actual target in filename order, with read-only post-apply checks. The repository has no automatic migration runner.
2. **Prepare a production service topology.** Root `docker-compose.yml` builds the web **development** target, sets `NODE_ENV=development`, exposes service ports, and uses Keycloak `start-dev` under its local profile. It is a local stack, not an MVP production manifest. Define target hosting, HTTPS/public URLs, private service networking, Redis persistence, database access, image versions and a separate production web build.
3. **Set release configuration and protect secrets.** Provide database credentials, web session and Keycloak client secrets, QR signing secret, face embedding encryption key and optional Expo access token through the target secret store. Align issuer/JWKS, web redirect URI, Core API and face-service URLs across server and Android. `EXPO_PUBLIC_CORE_API_URL` and `EXPO_PUBLIC_FACE_VERIFICATION_API_URL` need reachable HTTPS values at mobile build time; their code fallbacks target the Android emulator (`10.0.2.2`).
4. **Turn on and prove liveness deliberately.** Face-service `LIVENESS_ENFORCEMENT_ENABLED` defaults to `false` and is not passed by root Compose. The deployment must set it explicitly after a physical-device end-to-end test. Confirm model download/loading, resource needs, image processing, evidence validation, attempt accounting and the face embedding encryption key on the target host.
5. **Prove notifications on Android.** The API starts push and reminder workers by default. The unapplied notification/retry/idempotency migrations are prerequisites. Confirm push project credentials, token registration/revocation, trigger rows, delivery/receipts, reminders and deep links on a real Android build. Decide whether workers run with the API or in a dedicated single process before scaling replicas.
6. **Run the roadmap checkpoints against real services.** §26 of `FinalDevPlan/NewInstructions.md` defines CP1–CP8: initial check-in, QR batches, liveness, finalization, web/mobile agreement, notifications, policy and removal of compatibility behavior. Passing source CI and merging the PRs do not establish these checkpoints on the target database/device.
7. **Add operational proof.** Confirm service and DB health, logs/alerts, backup/restore rehearsal, a deploy rollback procedure, and a release owner. `/health` is a basic process response; `/health/db` is the explicit database check. No deployment workflow or release runbook was found under `.github/workflows` (which currently has only the three CI workflows).

## Review limits

This was a repository and GitHub CI review. It did not read live deployment settings, connect to Supabase or Keycloak, build an Android artifact, run migrations, or perform a physical-device check. The migration state above is the repository's last recorded live observation, not a fresh query in this review. No deployed MVP is claimed.

The release sequence and acceptance criteria are in [mvp-deployment-plan.md](mvp-deployment-plan.md).
