# Database Migrations

Small, numbered, forward-only SQL files that change the UniAttend application
schema in Supabase PostgreSQL.

The files in the parent `database/` folder are full baseline dumps
(`smart_attendance_db_clean.sql`) and seed data (`smart_attendance_seed.sql`).
They describe the schema as it was first created. Everything that changed after
that lives here.

## Order Of Application

For a brand new database:

1. `database/smart_attendance_db_clean.sql` (baseline schema)
2. every file in `database/migrations/` in ascending number order
3. `database/smart_attendance_seed.sql` (optional development data)

For an existing database: apply only the migrations that have not run yet.

## Naming

New migrations use a dated prefix:

```text
YYYYMMDD_NN_short_description.sql
YYYYMMDD_NN_short_description_rollback.sql   (optional)
```

`YYYYMMDD` is the date the file is written and `NN` is a two-digit sequence that
is unique within that date across the whole folder. Check the folder before
picking `NN`, and give a migration a prefix that sorts after every migration it
depends on.

Older files use two earlier styles that are kept as they are: `0001`/`0002`
(four-digit, application schema) and `001`-`006` (three-digit, face
verification). A new four-digit number would be ambiguous next to the
three-digit family, which is why dated prefixes took over from
`20260814_add_qr_batch_mode.sql` onwards.

**Apply order is plain filename order**, which keeps the families in the order
they were written:

```text
0001 -> 0002 -> 001 ... 006 -> 20260814 -> 2026MMDD_NN ...
```

Never renumber or edit a migration that has already been applied to a shared
database; add a new one instead.

## Rules

- Migrations must be additive. Do not drop or rename columns that existing code
  or historical data depends on.
- Wrap each migration in `BEGIN; ... COMMIT;`.
- Prefer `IF NOT EXISTS` so a re-run is harmless.
- Never write database credentials into a migration file, a rollback file, or
  the command used to run one.
- These migrations touch the UniAttend application database only. Keycloak owns
  its own separate PostgreSQL database and must never be modified from here.

## Applying A Migration

Shared Supabase is a team database, so migrations are applied manually and
deliberately. There is no automatic runner in this repository.

**Supabase SQL editor (recommended)**

1. Open the Supabase project → **SQL Editor** → **New query**.
2. Paste the whole contents of the migration file.
3. Press **Run** and confirm it reports success.

**psql**

```powershell
psql "$env:DB_URI" -v ON_ERROR_STOP=1 -f database/migrations/0001_add_keycloak_user_id.sql
psql "$env:DB_URI" -v ON_ERROR_STOP=1 -f database/migrations/0002_add_session_geofence_snapshot.sql
```

Read the connection string from an environment variable as shown. Do not type a
password on the command line, where it would land in shell history.

## Verifying

```sql
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'identity'
  AND table_name = 'users'
  AND column_name = 'keycloak_user_id';

SELECT indexname
FROM pg_indexes
WHERE schemaname = 'identity'
  AND indexname = 'uq_users_keycloak_user_id';
```

Both queries should return exactly one row.

For `0002_add_session_geofence_snapshot`:

```sql
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'attendance_session'
  AND table_name = 'session_geofences'
  AND column_name IN ('centre_latitude', 'centre_longitude', 'radius_m')
ORDER BY column_name;

SELECT conname
FROM pg_constraint
WHERE conrelid = 'attendance_session.session_geofences'::regclass
  AND conname LIKE 'ck_session_geofences_%'
ORDER BY conname;
```

The first query should return three nullable numeric columns. The second should
return the six snapshot and policy constraints added by the migration. Nullable
snapshot columns preserve legacy sessions that have no resolvable classroom;
the all-or-none constraint prevents partially configured snapshots.

## Verifying A Migration Before It Reaches Supabase

Shared Supabase is a team database, so prove a migration works on a throwaway
local one first. This uses Docker and touches nothing remote:

```powershell
docker run -d --name uniattend-sqlcheck -e POSTGRES_PASSWORD=throwaway_local_check -p 55432:5432 postgres:16-alpine

docker exec -i uniattend-sqlcheck psql -U postgres -d postgres -v ON_ERROR_STOP=1 < database/smart_attendance_db_clean.sql
docker exec -i uniattend-sqlcheck psql -U postgres -d postgres -v ON_ERROR_STOP=1 < database/migrations/0001_add_keycloak_user_id.sql
docker exec -i uniattend-sqlcheck psql -U postgres -d postgres -v ON_ERROR_STOP=1 < database/migrations/0002_add_session_geofence_snapshot.sql
docker exec -i uniattend-sqlcheck psql -U postgres -d postgres -v ON_ERROR_STOP=1 < database/smart_attendance_seed.sql

# then run the verify queries above, and finally
docker rm -f uniattend-sqlcheck
```

The password above is for a disposable container that exists for a few minutes
and is never reachable from outside the machine. Never reuse it anywhere, and
never substitute a real Supabase credential into these commands.

## Migration Log

**This table reflects live database state, last confirmed 2026-09-22 by read-only
`information_schema` / `pg_constraint` / `pg_indexes` queries against the shared
Supabase database — not by re-running the migration files.** See "How This Table
Is Kept Accurate" below before editing it again.

| Migration | Purpose | Verified locally | Applied to shared Supabase |
| --- | --- | --- | --- |
| `0001_add_keycloak_user_id` | Adds `identity.users.keycloak_user_id` plus a partial unique index, so a Keycloak `sub` claim resolves to an internal application user | Yes — see below | **Applied.** Confirmed live 2026-09-22: column and `uq_users_keycloak_user_id` both present |
| `0002_add_session_geofence_snapshot` | Adds frozen centre coordinates and radius plus snapshot and policy checks to `attendance_session.session_geofences` | Yes - PostgreSQL 16, see below | **Applied.** Confirmed live 2026-09-22: all three snapshot columns and all six `ck_session_geofences_*` checks present |
| `20260920_01_attendance_lifecycle_columns` | Additive columns for the attendance lifecycle: initial check-in state on `verification_attempts`, `qr_batch_id` on `qr_validation_attempts` (backfilled for static batches), and void fields on `qr_token_batches`, plus their indexes and the void consistency check | Yes - PostgreSQL 16, see below | **Applied.** Confirmed live 2026-09-22: `checked_in_at`, `initial_check_in_status`, `qr_batch_id`, `voided_at`, `voided_by`, `void_reason` all present |
| `20260920_02_attendance_check_in_state` | Backfills the initial check-in of attempts that already completed, renames the `completed` status to `checked_in`, and adds CHECK constraints for the frozen status vocabulary | Yes - PostgreSQL 16, see below | **Applied.** Confirmed live 2026-09-22: all three `ck_verification_attempts_*` checks present |
| `20260920_03_final_attendance_constraints` | Renames the record source `manual_review` to `manual` and adds CHECK constraints for the final attendance status and source vocabularies, and for the recorder and reason a manual record must carry | Yes - PostgreSQL 16, see below | **Applied.** Confirmed live 2026-09-22: all three `ck_attendance_records_*` checks present, and every existing `record_source` value is `automatic` or `manual` — no `manual_review` rows remain |
| `20260921_01_attendance_policies` | Adds the institution attendance policy table, its range checks and single-active index, then seeds the 15/10/5 defaults without changing face verification configuration | Not documented — no throwaway-database exercise for this file is recorded in this README | **Applied.** Confirmed live 2026-09-22: all three `ck_attendance_policies_*` checks present, one active row (`check_in_window_minutes=15, late_threshold_minutes=10, qr_default_validity_minutes=5`) |
| `20260921_02_notification_indexes_and_types` | Adds the `ATTENDANCE_SESSION_CANCELLED` notification type and four performance indexes for active Android device tokens, visible student notifications, and queued delivery attempts | Not documented — no throwaway-database exercise for this file is recorded in this README; it is additive and guarded (`ON CONFLICT ... DO UPDATE`, `IF NOT EXISTS`) in the same style as the others | **NOT APPLIED.** Confirmed live 2026-09-22: `ATTENDANCE_SESSION_CANCELLED` is absent from `notification.notification_types`, and none of the four indexes exist. **Consequence:** `NotificationProducer.session_cancelled` writes that type code, the insert violates `FK_notifications_notification_type`, and the surrounding `announce()` helper catches and logs the failure — so every session cancellation today silently loses its notification. Apply this migration to fix that. |
| `20260922_02_push_delivery_retry_schedule` | Adds the durable retry schedule used by the push worker, migrates legacy `pending` attempts to `queued`, and indexes ready queue scans | Not yet verified against a throwaway PostgreSQL database | **NOT APPLIED.** Apply only after `20260921_02_notification_indexes_and_types`. |
| `20260922_01_session_check_in_explicit_fields` | Adds three boolean flags to `attendance_session.sessions` (`check_in_opens_at_explicit`, `check_in_closes_at_explicit`, `late_after_at_explicit`) recording which check-in timestamps a lecturer explicitly supplied at creation, so a later activation can recompute only the policy-derived ones | Not documented — no throwaway-database exercise for this file is recorded in this README; it is additive and defaulted (`IF NOT EXISTS`, `DEFAULT false`) in the same style as the others | **NOT APPLIED** as of 2026-09-22 (written the same day, not yet run against shared Supabase). **Not additive to the running code**, unlike most migrations in this log: the code that reads these columns (session activation) is written on the same branch that introduces this file, so apply this migration to shared Supabase **before** that code is deployed — the same ordering rule `20260920_02`'s row documents. Applying it early is harmless either way; every existing row simply backfills to `false` ("policy-derived"), which is the correct reading for a row that predates this feature entirely. |

### What The Local Verification Confirmed

`0001` was applied to PostgreSQL 16 loaded with `smart_attendance_db_clean.sql`
and `smart_attendance_seed.sql`, and the following all held:

- The column and the partial unique index are created exactly as written.
- Re-running the migration is harmless. It reports "already exists, skipping"
  and does not error, so a repeated run cannot damage anything.
- All ten seeded users coexist with `keycloak_user_id IS NULL`, because the
  unique index is partial.
- A second user cannot take a `keycloak_user_id` that is already in use: the
  index rejects it. One Keycloak account maps to at most one application user.
- Every legacy authentication column survives (`password_hash`,
  `account_status`, `failed_login_attempts`, `locked_until`,
  `must_change_password`) along with `identity.refresh_tokens`,
  `identity.password_reset_tokens`, `identity.roles` and `identity.user_roles`.
- Row counts are unchanged. The migration adds a column and reads nothing.
- The rollback script removes the column and index, leaves all user and profile
  rows intact, and the migration re-applies cleanly afterwards.

### What The Attendance Lifecycle Local Verification Confirmed

`20260920_01` and `20260920_02` were applied in order to PostgreSQL 16 loaded
with the baseline, `0001`, `0002` and the development seed, without connecting
to Supabase. Because the seed contains no verification attempts, representative
legacy rows were inserted into the throwaway database first: attempts that
completed before and after the session's `late_after_at`, one `completed`
attempt with no timestamps at all, an `in_progress` attempt, a `failed`
attempt, and an attempt whose status the manual-review retry path had cleared to
NULL. The following all held:

- Both migrations apply cleanly in filename order, and re-running either is
  harmless — `20260920_01` reports "already exists, skipping" throughout, and
  `20260920_02` finds its work already done.
- The backfill sets `checked_in_at` from `completed_at` and derives lateness
  from the session threshold: the attempt finishing before it became
  `checked_in`, the one finishing after it became `late_checked_in`.
- A `completed` attempt with no timestamps survives the rename with
  `checked_in_at` left NULL, rather than being dropped or given a fabricated
  time.
- `in_progress`, `failed` and NULL statuses are untouched. NULL remains legal,
  so the lecturer's manual-review retry button keeps working.
- After the migration the database rejects `status = 'completed'`, any invented
  status, any invented `initial_check_in_status`, a `checked_in_at` without an
  outcome, and an outcome without a `checked_in_at`. A valid pair is accepted.
- Planting an unrecognised status (`'abandoned'`) makes `20260920_02` refuse to
  run, naming the offending value, and **nothing** is left half-applied: no rows
  renamed and no constraints added, because the guard runs inside the same
  transaction.
- The rollback drops the three constraints and returns `checked_in` to
  `completed`, after which the migration re-applies successfully. It leaves
  `checked_in_at` and `initial_check_in_status` populated on purpose; removing
  those columns is `20260920_01`'s rollback, which is a separate later step.

### What The Final Attendance Local Verification Confirmed

`20260920_03` was applied to PostgreSQL 16 loaded with the baseline, `0001`,
`0002`, the QR batch migration, the seed and both earlier lifecycle migrations,
without connecting to Supabase. The seed has no attendance records, so four were
inserted first to mirror the real data: two automatic rows and two
`manual_review` rows, each with a recorder and a reason. The following all held:

- Both `manual_review` rows became `manual`. The automatic rows and every other
  column were left alone.
- The database now rejects an invented status (`excused`, or a verification word
  like `checked_in`), an invented source (`system`, or the old `manual_review`),
  and a manual record with no reason, a blank reason, or no recorder. An
  automatic record with no recorder and no reason, and a complete manual record,
  are accepted.
- Re-running the migration is harmless.
- An unrecognised status, or a manual record with no reason, makes it refuse to
  run and name the problem. In both cases nothing was renamed and no constraint
  was added, because the check runs inside the same transaction.
- The rollback drops the three constraints and returns every `manual` record to
  `manual_review`, after which the migration re-applies cleanly.

### What The 0002 Local Verification Confirmed

`0002` was applied to PostgreSQL 16 loaded with the baseline and development
seed, without connecting to Supabase. The following all held:

- The existing active session was backfilled from its timetable classroom.
- Re-running the migration did not overwrite the frozen snapshot after the
  classroom coordinates and radius changed.
- Partial snapshots, out-of-range coordinates, and negative policy values were
  rejected by database checks.
- The rollback removed only the three snapshot columns and six checks. Session
  geofence rows and verification-attempt tables remained intact.
- The migration re-applied successfully after rollback.

### What `20260921_02` Does — And Why It Still Isn't Applied

`20260921_02` adds the `ATTENDANCE_SESSION_CANCELLED` notification type and performance indexes
for active Android device tokens, visible student notifications, and queued delivery attempts.

Unlike the migrations above, this one has not been through the throwaway-PostgreSQL verification
exercise this README otherwise documents, so there is no confirmed-behaviour section to report here.
What is confirmed is its state on the shared database: as of 2026-09-22, read-only queries against
`notification.notification_types` and `pg_indexes` show the type row and all four indexes absent.

This is a live gap, not a hypothetical one: `NotificationProducer.session_cancelled`
(`services/core-backend/modules/notification/producer/service.py`) already writes
`type_code="ATTENDANCE_SESSION_CANCELLED"` on the assumption that this migration has run. Every
session cancellation currently fails that insert against `FK_notifications_notification_type`, and
the failure is swallowed by the `announce()` helper (`modules/contracts/announce.py`), so a lecturer
cancelling a session sees no error and the affected students receive no notification.

**Apply this migration before relying on cancellation notifications.** It is additive and guarded —
`ON CONFLICT (code) DO UPDATE` for the type row, `IF NOT EXISTS` for every index — so it is safe to
run against the current shared state.

### How This Table Is Kept Accurate

The "Applied to shared Supabase" column is a claim about the live database, and it goes stale the
moment someone applies a migration without updating it — which is exactly what happened before this
row was corrected on 2026-09-22 (see `.local-plans/final-development/README.md`, Phase 1, for the
read-only queries used). Two rules keep it trustworthy going forward:

- **State it from evidence, not from memory.** Before changing a row from "Not applied" to
  "Applied" (or the reverse), run a read-only query against the actual column, constraint, or index
  the migration creates — the patterns above show what that looks like — and note the date.
- **Applying a migration and updating this table are the same change.** If you apply
  `20260921_02` (or any future migration) to shared Supabase, edit its row in the same sitting. A
  migration log that lags reality is worse than no log, because it actively misdirects the next
  person who reads it.
