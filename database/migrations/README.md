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

| Migration | Purpose | Verified locally | Applied to shared Supabase |
| --- | --- | --- | --- |
| `0001_add_keycloak_user_id` | Adds `identity.users.keycloak_user_id` plus a partial unique index, so a Keycloak `sub` claim resolves to an internal application user | Yes — see below | **Not applied.** Pending a manual run by someone with Supabase project access |
| `0002_add_session_geofence_snapshot` | Adds frozen centre coordinates and radius plus snapshot and policy checks to `attendance_session.session_geofences` | Yes - PostgreSQL 16, see below | **Not applied.** Supabase access is blocked; do not apply remotely |
| `20260920_01_attendance_lifecycle_columns` | Additive columns for the attendance lifecycle: initial check-in state on `verification_attempts`, `qr_batch_id` on `qr_validation_attempts` (backfilled for static batches), and void fields on `qr_token_batches`, plus their indexes and the void consistency check | Yes - PostgreSQL 16, see below | **Not applied.** Apply only after the O0 schema audit confirms `0001` and `0002` are in place |
| `20260920_02_attendance_check_in_state` | Backfills the initial check-in of attempts that already completed, renames the `completed` status to `checked_in`, and adds CHECK constraints for the frozen status vocabulary | Yes - PostgreSQL 16, see below | **Not applied.** Not additive: apply it together with the release that replaces the completion endpoint, never ahead of it |
| `20260920_03_final_attendance_constraints` | Renames the record source `manual_review` to `manual` and adds CHECK constraints for the final attendance status and source vocabularies, and for the recorder and reason a manual record must carry | Yes - PostgreSQL 16, see below | **Not applied.** Not additive: apply it together with the release that writes `manual`, never ahead of it |
| `20260921_01_attendance_policies` | Adds the institution attendance policy table, its range checks and single-active index, then seeds the 15/10/5 defaults without changing face verification configuration | Pending local PostgreSQL verification | **Not applied.** Apply before enabling C17 or binding the policy provider |

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

### What The 20260921_02 Notification Indexes and Types Confirmed

`20260921_02` adds the `ATTENDANCE_SESSION_CANCELLED` notification type and performance indexes
for active Android device tokens, visible student notifications, and queued delivery attempts.

