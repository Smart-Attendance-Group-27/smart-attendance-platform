# MVP deployment readiness review

**Reviewed:** 2026-09-23

**Reviewer:** Manushan deployment branch review

**Source:** `origin/main` at `c7cde884bdc90e8e3e68b92d08a658b77916954b`

**Decision:** The repository now contains a production Compose model, environment validation, schema verification, smoke checks and a concrete operator runbook. The first MVP can proceed to a preview deployment after real environment values and target database evidence are supplied. Liveness remains deferred; pilot attendance sessions must have face verification disabled.

## Current status

| Area | Current repository evidence | Readiness assessment |
| --- | --- | --- |
| Integration | The final integration PR #84 is merged. The QR evidence, notification producer and attendance policy providers are bound in `services/core-backend/modules/contracts/providers.py`. | Core development integration is present. Merged code alone does not prove a deployed flow. |
| CI | Web, Backend and Mobile CI passed on the reviewed `main` SHA. Web runs typecheck, lint, tests and a production build; Backend runs both Python test suites; Mobile runs typecheck, lint and tests. | Good source baseline. Deployment CI now validates the production model, rebuilds a fresh schema and builds all production images. It does not build an Android release artifact or test a complete device flow. |
| Services | Production Docker targets now run as unprivileged users. `docker-compose.production.yml` provides explicit health checks, persistent Redis/model volumes, private service networking, loopback ingress bindings and external PostgreSQL/Keycloak configuration. | The repository service model is deployable. The real host, HTTPS ingress, secrets and external services must still be supplied by the operator. |
| Mobile | Expo EAS profiles and Android package metadata exist; the app implements attendance, face/QR and notification flows. | No verified release APK/AAB or physical Android acceptance result is recorded by this review. |
| Database | Baseline and all forward migrations, including face runtime schema hardening, apply cleanly to a fresh PostgreSQL 16 database. `deployment/verify_mvp_schema.sql` checks application-required tables, columns, defaults, constraints and indexes. | Repository schema reconstruction is proven. The target database must still be backed up, reconciled and verified because its actual migration state is external to this review. |

## Release gates and current gaps

1. **Reconcile and apply outstanding application migrations.** The migration log marks four notification/session migrations as **not applied** to shared Supabase on 2026-09-22. The new `20260923_01_face_schema_runtime_constraints.sql` migration is also required before enrollment or verification attempts because it supplies server defaults and required constraints expected by the face ORM. Back up the target, apply only its missing forward migrations in filename order, then run `deployment/verify_mvp_schema.sql`. There is deliberately no automatic live migration runner.
2. **Provision the production target.** The repository now has a production Compose model and runbook. Supply the Docker host or equivalent platform, HTTPS ingress and DNS, external PostgreSQL and Keycloak, persistent storage and the reviewed image tag. Root `docker-compose.yml` remains the local development stack.
3. **Set release configuration and protect secrets.** Start from `deployment/mvp.env.example`, store the resulting values in the target secret store and run `deployment/validate_env.py`. Provide database credentials, web session and Keycloak client secrets, QR signing secret, face embedding encryption key and optional Expo access token. `EXPO_PUBLIC_CORE_API_URL` and `EXPO_PUBLIC_FACE_VERIFICATION_API_URL` require reachable HTTPS values at mobile build time.
4. **Keep liveness outside the first release.** `docker-compose.production.yml` explicitly leaves liveness enforcement off. Because secure face attendance still depends on the unfinished mobile evidence flow, every first-release pilot session must be created with face verification disabled. The face service may be deployed and tested through readiness without treating that result as attendance.
5. **Prove notifications on Android.** Push and reminder workers default off in the production model. After applying the notification migrations, confirm Expo credentials, token registration/revocation, trigger rows, delivery/receipts, reminders and deep links on a real Android build. Enable each worker deliberately and keep a single worker instance until duplicate-delivery behavior is proven.
6. **Run the in-scope roadmap checkpoints against real services.** Section 26 of `FinalDevPlan/NewInstructions.md` defines CP1-CP8. The first deployment can exercise initial check-in, QR batches, finalization, web/mobile agreement, notifications and policy. Liveness and secure face attendance remain deferred and must not be recorded as passed.
7. **Collect operational proof.** The deployment workflow, smoke script and runbook now exist. The operator must still record target health, bounded logs/alerts, backup and restore evidence, rollback ownership, image IDs, migration output and physical-device results. `/health` is a process check; `/health/db` is the database dependency check.

## Review limits

This was a repository, local container build, disposable PostgreSQL and GitHub CI review. It did not read live deployment settings, connect to the target Supabase or Keycloak, build an Android artifact, modify the target database, or perform a physical-device check. No deployed MVP is claimed.

The release sequence and acceptance criteria are in [mvp-deployment-plan.md](mvp-deployment-plan.md). Concrete commands are in [mvp-deployment-runbook.md](mvp-deployment-runbook.md).
