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

```text
NNNN_short_description.sql
NNNN_short_description_rollback.sql   (optional)
```

`NNNN` is a zero-padded sequence number. Never renumber or edit a migration
that has already been applied to a shared database; add a new one instead.

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
