# UniAttend Backend Integration And Manual Testing Guide

How to run the first end-to-end slice by hand:

```text
Keycloak login  ->  FastAPI validates the token  ->  Keycloak user maps to a
Supabase application user  ->  FastAPI returns the student profile  ->  the
Expo profile screen shows it
```

Written for someone setting this up for the first time. Follow it in order.

> **Credentials rule.** The Supabase password lives in exactly one place:
> `services/core-backend/.env`, which is untracked. It never goes into
> `.env.example`, Postman files, mobile `EXPO_PUBLIC_*` variables, tests,
> documentation, commit messages or chat. Never paste a real access token or a
> connection URI into a ticket.

---

## 1. Required Software

| Software | Why | Notes |
| --- | --- | --- |
| Docker Desktop | Runs Keycloak and its own PostgreSQL | Must be running before you start Keycloak |
| Python 3.11, 3.12 or 3.13 | Runs the FastAPI backend | Install from python.org. See the warning below |
| Node.js 24.x | Runs the Expo app and the test suite | Matches the CI version |
| Postman | Manual API testing | Desktop app, so it can reach `localhost` |
| A code editor | Editing `.env` files | Any |

> **Windows / MSYS2 warning.** If `python --version` points at
> `C:\msys64\ucrt64\bin\python.exe`, dependency installation fails: several
> packages have no MinGW build. Use the python.org CPython instead. Check with:
>
> ```powershell
> py -0p
> ```

Redis is **not** needed for this slice. It is used for temporary verification
and session data in later milestones.

---

## 2. Create The Local Environment Files

### 2.1 Backend

Copy the example:

```powershell
Copy-Item services/core-backend/.env.example services/core-backend/.env
```

Open `services/core-backend/.env` and fill it in.

**Where you enter the Supabase password:** in `DB_URI`, replacing `PASSWORD`.
Do not add quotes around the password itself, and if it contains `@`, `:`, `/`
or `#`, percent-encode those characters.

```env
DB_URI="postgresql://POOLER_USER:YOUR_ROTATED_PASSWORD@aws-0-ap-northeast-2.pooler.supabase.com:5432/postgres"
DB_SSL_MODE="require"
```

`DB_URI` takes precedence. When it is set, `DB_HOST`, `DB_PORT`, `DB_NAME`,
`DB_USER` and `DB_PASSWORD` are ignored entirely. Use one style, not both. If
you prefer the individual fields, leave `DB_URI` empty and fill all of
`DB_HOST`, `DB_USER` and `DB_PASSWORD`.

Get the pooler user and host from **Supabase → Project Settings → Database →
Connection pooling**. The pooler user usually looks like
`postgres.<project-ref>`.

Then set the Keycloak block:

```env
KEYCLOAK_EXPECTED_ISSUER="http://localhost:8080/realms/uniattend"
KEYCLOAK_JWKS_URL="http://localhost:8080/realms/uniattend/protocol/openid-connect/certs"
KEYCLOAK_AUDIENCE="uniattend-api"
```

**These two are not the same setting.** `KEYCLOAK_EXPECTED_ISSUER` must equal
the `iss` claim inside the token, character for character. `KEYCLOAK_JWKS_URL`
is fetched by the backend itself and only has to be reachable from the laptop.
See section 9 when testing from a phone.

`TOKEN_SECRET` can stay empty. It predates Keycloak, nothing reads it, and it is
never used to validate tokens. It is scheduled for removal.

Confirm the file is ignored:

```powershell
git check-ignore -v services/core-backend/.env
```

That must print a matching `.gitignore` rule. If it prints nothing, stop and fix
`.gitignore` before continuing.

### 2.2 Mobile

```powershell
Copy-Item apps/mobile/.env.example apps/mobile/.env.local
```

```env
EXPO_PUBLIC_KEYCLOAK_HOST=192.168.1.5
EXPO_PUBLIC_CORE_API_URL=http://192.168.1.5:8000
```

Use your laptop's own LAN IPv4 address. Find it with `ipconfig`.

**Nothing secret goes in an `EXPO_PUBLIC_*` variable.** Anything with that
prefix is compiled into the app bundle and readable by anyone holding the APK.
No database credentials, no Supabase service key, no Keycloak client secret.
The mobile client is a public OAuth client precisely so that it needs no secret.

---

## 3. Start Keycloak And Its Database

From the repository root:

```powershell
docker compose --env-file infra/local/keycloak/.env.example -f infra/local/keycloak/docker-compose.yml up -d
```

This starts two containers: `uniattend-keycloak-db` (PostgreSQL, used only by
Keycloak) and `uniattend-keycloak`. Check them:

```powershell
docker compose -f infra/local/keycloak/docker-compose.yml ps
```

Open <http://localhost:8080/admin> and sign in with `admin` / `admin` (local
development only).

### 3.1 Apply The Updated Realm

The realm file now contains three clients:

| Client | Purpose |
| --- | --- |
| `uniattend-api` | Bearer-only resource server. Never logs anyone in. It exists so tokens can carry the `uniattend-api` audience |
| `uniattend-mobile` | The Expo app. Public, PKCE, no direct grants |
| `uniattend-postman` | Manual API testing. Public, PKCE, no direct grants |

`uniattend-mobile` and `uniattend-postman` each carry an **audience mapper** that
adds `uniattend-api` to the access token's `aud` claim. Without it the backend
rejects every token with *"Access token audience is not accepted"*, because
Keycloak does not add a resource server to `aud` on its own.

Keycloak imports the realm only when its database is empty. If you already had
the realm, choose one:

**Option A — reset the local Keycloak database (destroys local test users):**

```powershell
docker compose -f infra/local/keycloak/docker-compose.yml down -v
docker compose --env-file infra/local/keycloak/.env.example -f infra/local/keycloak/docker-compose.yml up -d
```

**Option B — add the pieces by hand in the admin console (keeps test users):**

1. **Clients → Create client** → client ID `uniattend-api` → Next → turn
   **Client authentication** on and disable every flow → Save.
2. **Clients → Create client** → client ID `uniattend-postman` → Next →
   Client authentication **off**, Standard flow **on**, Direct access grants
   **off** → Next → Valid redirect URIs: `https://oauth.pstmn.io/v1/callback`
   → Save. Then **Advanced → Proof Key for Code Exchange** → `S256`.
3. For **both** `uniattend-mobile` and `uniattend-postman`:
   **Client scopes → <client>-dedicated → Add mapper → By configuration →
   Audience** → Name `uniattend-api-audience`, Included Client Audience
   `uniattend-api`, Add to access token **on** → Save.

### 3.2 Create The Test Users

**Realm roles** (`student`, `lecturer`, `administrator`) already exist.

In **Users → Add user**, create these five, then set a password under
**Credentials** with *Temporary* off, and assign roles under **Role mapping**.
Do not record the passwords anywhere.

| # | Username | Realm role | Purpose |
| --- | --- | --- | --- |
| 1 | `student.linked` | `student` | Linked active student — the happy path |
| 2 | `lecturer.linked` | `lecturer` | Linked lecturer — wrong role |
| 3 | `student.unlinked` | `student` | Never linked to an application user |
| 4 | `student.inactive` | `student` | Linked to a non-active application user |
| 5 | `student.noprofile` | `student` | Linked and active but has no profile row |

For each user you must link, copy its Keycloak **ID** from the user's Details
tab. That value is the `sub` claim.

---

## 4. Apply The Database Migration

**Status: not applied to Supabase, but verified locally.** The migration exists
in the repository and has been proven against a throwaway PostgreSQL 16 database
loaded with this repository's own baseline schema and seed data. It applies
cleanly, is safe to re-run, keeps every legacy authentication column and table,
changes no rows, and rolls back without data loss. See
`database/migrations/README.md` for the full result and for how to repeat the
check yourself.

Someone with Supabase project access still has to run it there.

1. Open **Supabase → SQL Editor → New query**.
2. Paste the whole contents of
   `database/migrations/0001_add_keycloak_user_id.sql`.
3. Press **Run**.

Verify:

```sql
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'identity'
  AND table_name = 'users'
  AND column_name = 'keycloak_user_id';
```

One row. The migration is additive: no column is dropped, no password, refresh
token, reset token, lockout field or legacy role is touched, and Keycloak's own
database is not involved.

### 4.1 Link The Test Users

Run these in the Supabase SQL editor, replacing each `KEYCLOAK_ID_OF_*` with the
ID you copied in section 3.2. These are **application** records; passwords are
not involved anywhere here.

```sql
-- 1. Linked active student (uses seeded student 230701A)
UPDATE identity.users
SET keycloak_user_id = 'KEYCLOAK_ID_OF_student.linked'
WHERE email = '230701a@student.uniattend.test';

-- 2. Linked lecturer
UPDATE identity.users
SET keycloak_user_id = 'KEYCLOAK_ID_OF_lecturer.linked'
WHERE email = 'n.perera@staff.uniattend.test';

-- 3. Unlinked user: do nothing at all. student.unlinked must have no row here.

-- 4. Linked but inactive application user
UPDATE identity.users
SET keycloak_user_id = 'KEYCLOAK_ID_OF_student.inactive',
    account_status = 'suspended'
WHERE email = '230702b@student.uniattend.test';

-- 5. Linked active student with no profile row
INSERT INTO identity.users (id, email, account_status, failed_login_attempts,
                            must_change_password, keycloak_user_id,
                            created_at, updated_at)
VALUES (gen_random_uuid(), 'noprofile@student.uniattend.test', 'active', 0,
        false, 'KEYCLOAK_ID_OF_student.noprofile', now(), now());
```

Check the links without exposing anything sensitive:

```sql
SELECT email, account_status, keycloak_user_id IS NOT NULL AS is_linked
FROM identity.users
ORDER BY email;
```

To undo case 4 afterwards:

```sql
UPDATE identity.users SET account_status = 'active'
WHERE email = '230702b@student.uniattend.test';
```

---

## 5. Start FastAPI

```powershell
cd services/core-backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload
```

To let a phone reach it, bind to all interfaces:

```powershell
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Startup prints the app name and `Database pool ready (ssl_mode=require,
pool=1-5)`. It never prints the URI, the user or the password. If Keycloak
settings are missing you get a warning at startup and a `503` from
authenticated endpoints.

Allow port 8000 through Windows Firewall the first time you test from a phone.

---

## 6. Check Health

```powershell
curl.exe http://127.0.0.1:8000/health
curl.exe http://127.0.0.1:8000/health/db
```

Expected:

```json
{"status":"ok"}
{"status":"ok","database":"connected"}
```

`/health/db` proves the pool opened, Supabase accepted the SSL connection and a
query returned. The pool closes cleanly on Ctrl+C.

### Diagnosing A `/health/db` Failure

Read the message in the uvicorn console, not the HTTP body.

| Symptom in the log | Likely cause | Fix |
| --- | --- | --- |
| `password authentication failed` | Wrong password, or an unencoded `@` `:` `/` `#` in it | Re-copy the rotated password and percent-encode specials |
| `role "postgres" does not exist` | Using `postgres` instead of the pooler user | Use `postgres.<project-ref>` from Connection pooling |
| `could not translate host name` | DNS or typo in the host | Check the host; confirm you are online |
| `connection timed out` | Network or firewall blocks outbound 5432 | Try another network; some campus Wi-Fi blocks it |
| `server does not support SSL` | `DB_SSL_MODE` wrong | Supabase requires SSL. Keep `require` |
| `Database configuration is incomplete...` | `.env` missing or not filled | Create it from `.env.example` |
| Works with `DB_HOST` but not `DB_URI` | Both styles half-filled | `DB_URI` wins. Use one style |
| `prepared statement ... already exists` | Pooler in transaction mode | Already handled: the pool sets `statement_cache_size=0` |

Never paste a real connection URI into a chat or ticket while debugging.

---

## 7. Run The Automated Tests

**Backend** (from `services/core-backend`, with the venv active):

```powershell
python -m pytest
```

102 tests. They never contact Keycloak and never touch shared Supabase: tokens
are signed with a locally generated RSA key, JWKS is served from memory and the
database is a fake.

**Mobile** (from the repository root):

```powershell
npm run typecheck --workspace=apps/mobile
npm run lint --workspace=apps/mobile
npm run test:ci --workspace=apps/mobile
```

165 tests.

---

## 8. Postman

### 8.1 Import

1. **Import** → `docs/postman/UniAttend_Backend_Foundation.postman_collection.json`
2. **Import** → `docs/postman/UniAttend_Local.postman_environment.json`
3. Select **UniAttend Local** in the environment dropdown, top right.

### 8.2 Add The Callback URL To Keycloak

Postman's browser flow returns to this exact URL, which must be listed under
**Valid redirect URIs** on the `uniattend-postman` client:

```text
https://oauth.pstmn.io/v1/callback
```

### 8.3 Get A Token With PKCE

1. Open the collection → **Authorization** tab. It is preconfigured as
   *OAuth 2.0*, grant type *Authorization Code (With PKCE)*, code challenge
   *S256*, client ID `{{postmanClientId}}`, no client secret.
2. Scroll down → **Get New Access Token**.
3. A browser window opens on Keycloak. Sign in as `student.linked`.
4. **Proceed** → **Use Token**.

There is no password grant here on purpose. Postman never sees the password;
Keycloak collects it in its own browser window.

### 8.4 Run The Requests

| # | Request | Expected |
| --- | --- | --- |
| 1 | Backend health | 200 |
| 2 | Database health | 200, `database: connected` |
| 3 | Current user without a token | 401 |
| 4 | Current user with a valid token | 200, internal UUID + roles |
| 5 | Student profile, student token | 200, profile fields |
| 6 | Student profile, lecturer token | 403 |
| 7 | Student profile, invalid token | 401 |
| 8 | Student profile, unlinked user | 404 |
| 9 | Linked student without a profile | 404 |

Requests 6, 8 and 9 need their own tokens. For each: run **Get New Access
Token** signing in as that user, copy the token, and paste it into the matching
environment variable (`lecturerAccessToken`, `unlinkedAccessToken`,
`studentWithoutProfileAccessToken`). **Clear those variables when you finish.**
They are marked secret and are never written to the repository.

Run everything at once with **Collection → Run**.

---

## 9. Which API URL To Use From Where

| Client | `EXPO_PUBLIC_CORE_API_URL` / Postman base URL | Why |
| --- | --- | --- |
| Postman on the laptop | `http://127.0.0.1:8000` | Same machine |
| Android Emulator | `http://10.0.2.2:8000` | `10.0.2.2` is the emulator's alias for the host laptop. `localhost` means the emulator itself |
| Physical phone | `http://<laptop-LAN-IP>:8000` | For example `http://192.168.1.5:8000` |

For a physical phone: the phone and the laptop must be on the same Wi-Fi
network, the laptop firewall must allow port 8000, and uvicorn must be started
with `--host 0.0.0.0`. Many public and campus networks isolate clients from each
other and will not work; a phone hotspot is a reliable fallback.

### The Issuer Must Still Match Exactly

This is the single most common failure.

The `iss` claim is whatever address the **client** used to reach Keycloak. A
phone signing in through `http://192.168.1.5:8080/realms/uniattend` gets that
string in `iss`. If the backend expects
`http://localhost:8080/realms/uniattend`, the token is rejected with 401 and
*"Access token issuer is not accepted"* — correctly, because a mismatched
issuer is exactly what token-substitution attacks look like.

So when you switch the mobile app to a LAN address, change the backend to match:

```env
KEYCLOAK_EXPECTED_ISSUER="http://192.168.1.5:8080/realms/uniattend"
KEYCLOAK_JWKS_URL="http://localhost:8080/realms/uniattend/protocol/openid-connect/certs"
```

The JWKS URL stays on `localhost`: the backend fetches that itself, and it never
has to match the token.

Restart uvicorn after changing `.env`. Settings are cached at startup.

Database credentials stay in the backend only. The mobile app never connects to
PostgreSQL and never sees Supabase.

---

## 10. Step-By-Step Mobile Verification

1. **Start Keycloak.**
   ```powershell
   docker compose --env-file infra/local/keycloak/.env.example -f infra/local/keycloak/docker-compose.yml up -d
   ```
2. **Start FastAPI.**
   ```powershell
   cd services/core-backend
   .\.venv\Scripts\Activate.ps1
   python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```
3. **Confirm database health.** Open `http://127.0.0.1:8000/health/db` and check
   for `"database":"connected"`. Do not continue until this passes.
4. **Start the Expo development build.**
   ```powershell
   npm run start --workspace=apps/mobile
   ```
   A development build is required, not Expo Go: the app uses
   `expo-secure-store`, `expo-auth-session` and `expo-camera`. Build once with
   `npm run android --workspace=apps/mobile`.
5. **Sign in as the linked student** (`student.linked`) through the Keycloak
   browser screen.
6. **Open the profile screen** by tapping the avatar on the dashboard.
7. **Confirm the data comes from Supabase.** It should show `230701A` /
   `Amal Perera`, not the mock `230736R` / `Manushan Hasanka`. Seeing the mock
   values means the real service is not wired up. Cross-check the uvicorn log
   for a `GET /api/v1/students/me/profile 200` line.
8. **Update a harmless test value** in Supabase:
   ```sql
   UPDATE academic.student_profiles
   SET first_name = 'Amal Test', updated_at = now()
   WHERE registration_number = '230701A';
   ```
9. **Reload the app** (press `r` in the Expo terminal, or reopen the profile
   screen) and confirm it now reads `Amal Test Perera`. This proves the screen
   reads live database data rather than anything cached or hard-coded. Restore
   the original value afterwards.
10. **Stop FastAPI** with Ctrl+C.
11. **Reload the profile screen.** It must show *"We couldn't load your
    profile"* with a **Retry** button. It must **not** show mock data and must
    not show a stale profile. This is the check that a silent mock fallback has
    not crept back in.
12. **Test a non-student role.** Sign out, restart FastAPI, sign in as
    `lecturer.linked`, and open the profile screen. Expect *"Student access
    required"*. Also try `student.unlinked` (expect *"Profile not found"*) and
    `student.inactive` (expect the forbidden state).

---

## 11. Manual Test Record

Fill this in as you go. Record evidence as a screenshot filename or a log line.
**Never record a password or an access token.** For evidence, mask any token as
`eyJ...<masked>`.

| Test ID | Test case | Precondition | Steps | Expected result | Actual result | Pass/Fail | Tester | Date | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MT-01 | API process is up | FastAPI running | GET `/health` | 200 `{"status":"ok"}` | | | | | |
| MT-02 | Supabase reachable over SSL | `.env` filled with rotated password | GET `/health/db` | 200 `database: connected` | | | | | |
| MT-03 | Startup leaks no credentials | FastAPI starting | Read the uvicorn console | No URI, user or password in the log | | | | | |
| MT-04 | Migration applied | Supabase access | Run the verify query in section 4 | One row for `keycloak_user_id` | | | | | |
| MT-05 | No token refused | FastAPI running | Postman request 3 | 401 + `WWW-Authenticate: Bearer` | | | | | |
| MT-06 | Malformed token refused | FastAPI running | Postman request 7 | 401 | | | | | |
| MT-07 | Expired token refused | A token older than its lifetime | Reuse an old token on `/api/v1/me` | 401 "expired" | | | | | |
| MT-08 | Wrong issuer refused | Set `KEYCLOAK_EXPECTED_ISSUER` to a wrong host, restart | Postman request 4 | 401 "issuer" | | | | | |
| MT-09 | Wrong audience refused | Remove the audience mapper, get a new token | Postman request 4 | 401 "audience" | | | | | |
| MT-10 | Valid student identified | `student.linked` linked and active | Postman request 4 | 200, internal UUID, `roles: ["student"]` | | | | | |
| MT-11 | Sensitive fields hidden | As MT-10 | Inspect the response body | No password, status or Keycloak fields | | | | | |
| MT-12 | Unlinked user refused | `student.unlinked` has no DB row | Postman request 8 | 404 | | | | | |
| MT-13 | Inactive user refused | `student.inactive` suspended | `/api/v1/me` with that token | 403 | | | | | |
| MT-14 | Student profile returned | `student.linked` has a profile | Postman request 5 | 200, correct registration number and name | | | | | |
| MT-15 | Lecturer refused | `lecturer.linked` linked | Postman request 6 | 403 "student role required" | | | | | |
| MT-16 | Missing profile reported | `student.noprofile` linked, no profile row | Postman request 9 | 404 | | | | | |
| MT-17 | Mobile shows real data | Steps 1–7 of section 10 | Open the profile screen | Supabase values, not mock values | | | | | |
| MT-18 | Mobile reflects a DB change | Step 8 of section 10 | Update the DB, reload | The new value appears | | | | | |
| MT-19 | No mock fallback on failure | FastAPI stopped | Reload the profile screen | Error state with Retry, no mock data | | | | | |
| MT-20 | Mobile rejects a lecturer | Signed in as `lecturer.linked` | Open the profile screen | "Student access required" | | | | | |
| MT-21 | Emulator reaches the backend | Emulator, `10.0.2.2` base URL | Sign in and open the profile | Profile loads | | | | | |
| MT-22 | Phone reaches the backend | Phone on the same Wi-Fi, LAN base URL, matching issuer | Sign in and open the profile | Profile loads | | | | | |

---

## 12. Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| 401 *"audience is not accepted"* | The audience mapper is missing | Section 3.1 |
| 401 *"issuer is not accepted"* | Backend issuer differs from the token's `iss` | Section 9 |
| 401 *"signing key is unknown"* | The realm was reimported and keys rotated | Wait ~30s or restart uvicorn |
| 404 on `/api/v1/me` with a valid token | `keycloak_user_id` is not set for that user | Section 4.1 |
| 403 on `/api/v1/me` | `account_status` is not `active` | Check `identity.users` |
| 403 on the profile with a student login | The `student` realm role is not assigned | Keycloak → Users → Role mapping |
| 503 on any authenticated endpoint | Keycloak settings missing from `.env` | Section 2.1, then restart |
| Mobile shows the network error state | Wrong `EXPO_PUBLIC_CORE_API_URL`, uvicorn not on `0.0.0.0`, or firewall | Section 9 |
| Mobile still shows mock data | Stale bundle | Restart Expo with `--clear` |
| `pip install` fails on `pydantic-core` | MSYS2 Python | Use python.org CPython. Section 1 |
