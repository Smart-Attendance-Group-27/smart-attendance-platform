# Web Dashboard & Backend Integration — Summary

This document explains everything that was built on the `feat/web-dashboard-integration`
branch: the new Next.js web dashboard, the FastAPI APIs that back it, the
authentication work that ties both the web app and the mobile app to Keycloak,
a mobile QR-auth fix, a product scope change around face verification, and the
local-testing fixes made while verifying all of this end to end on a real
phone and browser. It is written as a handoff document — read top to bottom
for the full picture, or jump to a section for one specific piece.

---

## 1. What this branch delivers, in one paragraph

Before this branch, the web app was a static QR-test page and the lecturer/admin
dashboards existed only as UI mockups over hardcoded mock data — there was no
real login, no real backend data, and no way for a lecturer or administrator to
actually use the system from a browser. This branch adds a full Next.js
dashboard with real Keycloak login, wires it to a large set of new FastAPI
endpoints for lecturer and administrator workflows, fixes an authentication gap
in the mobile app's QR verification flow, removes a feature the team decided
not to ship (lecturer-triggered repeat face verification), and adds CI checks
for the web app. It also includes a set of fixes discovered by actually running
the whole stack end to end — web browser, FastAPI backend, Keycloak, and a
physical Android phone on the same Wi-Fi network — which is where most of the
subtle bugs surfaced.

---

## 2. Web dashboard — authentication

The web dashboard needed real login before anything else could be meaningfully
tested, so this was built first.

- **Mock auth foundation first**: a session cookie, a data-access-layer (DAL)
  for reading the session, and role-guarded routing were built against a fake
  "mock" sign-in so the rest of the dashboard UI could be built and tested
  without depending on Keycloak being wired up yet.
- **Real Keycloak OIDC client**: a from-scratch OIDC client library was added
  (`apps/web`) implementing the Authorization Code flow with PKCE — discovery,
  authorization redirect, token exchange, refresh, and verification — matching
  the same identity provider (Keycloak) the mobile app already used.
- **New Keycloak client registered**: a dedicated `uniattend-web` Keycloak
  client was added in `infra/local/keycloak` (separate from the mobile app's
  client), since a server-rendered Next.js app and a mobile app have different
  redirect/token-handling requirements.
- **Session cookie design**: only the **refresh token** is stored in the
  session cookie, not the access token. Access tokens are minted server-side
  on demand from the refresh token. A short-lived "flow-state" cookie protects
  the OIDC redirect step (state/PKCE verifier) during login.
- **Login and callback routes**: real route handlers for `/api/auth/login` and
  the OIDC callback were added, and the previous mock sign-in was fully
  replaced with real Keycloak authentication and logout.
- **Test coverage**: unit tests were added for the OIDC client and the session
  DAL, covering the new token/session payload shape.

**Where to look:** `apps/web/src/lib/auth/` (OIDC client, session DAL),
`apps/web/src/app/api/auth/` (login/callback routes), `infra/local/keycloak/`.

---

## 3. Web dashboard — lecturer and administrator UI

The UI was built mock-data-first (so it could be designed and tested in
isolation), then wired to real APIs once the backend endpoints existed
(see §5).

**Shared foundation:**
- A reusable dashboard UI component library (buttons, form fields, data
  tables, activity lists, confirmation dialogs, status badges, line/bar
  charts) and a dashboard shell layout using the university's design tokens.
- Icon set and role-based navigation config, so lecturers and administrators
  see different nav items based on their Keycloak realm role.
- Loading, error, and not-found boundaries for every lecturer/admin route.
- Empty-state messaging wired through `DataTable` and `ActivityList` so
  screens don't look broken when a lecturer/admin has no data yet (e.g. no
  sessions created yet).

**Lecturer pages:**
- Overview dashboard, courses & timetable, session list with a live session
  monitor, a verification-review workspace (approve/reject flagged attendance
  attempts), and an attendance-reports page with charts.

**Administrator pages:**
- Full admin UI: user directory (with account activate/deactivate), academic
  data browser, classroom & geofence management (create/edit forms with an
  interactive map-style selection panel), policy controls, institution-wide
  reports, and an audit-log viewer.

**Service layer:** both lecturer and admin pages consume data through a
service-layer abstraction (not direct fetch calls in components), which is
what made it possible to build the UI against mock data first and then swap
in real API calls later (§5) with minimal component changes.

**Test coverage:** a Vitest unit/component test suite was added for the web
app (this is also what `npm run test:ci --workspace=apps/web` runs in CI).

---

## 4. Backend — new lecturer and administrator APIs

A large set of new FastAPI modules were added under
`services/core-backend/modules/`, following the existing
`modules/<domain>/<feature>/{route,service,repository,schemas,exception}.py`
convention.

**Authorization:** `CurrentLecturer` and `CurrentAdministrator` FastAPI
dependencies were added (alongside the existing `CurrentStudent`), so every
new endpoint can require the correct Keycloak realm role.

**Lecturer APIs:**
- Lecturer profile, course list, and timetable.
- Attendance-session lifecycle management (create/activate/close) and a
  live student-monitor view for an in-progress session.
- Manual attendance-review queue and decision endpoint (approve/reject a
  flagged attempt).
- Dashboard overview, per-course session reports, weekly attendance-trend
  data, and at-risk-student detection (students falling below an attendance
  threshold).

**Administrator APIs:**
- User directory and account-status (activate/deactivate) management.
- Read-only academic-data browsing.
- Reference-face governance (managing students' enrolled face references).
- Classroom and geofence CRUD.
- Audit-log read API.
- Dashboard overview and institution-wide attendance reports.

**Cross-cutting:**
- Audit logging was added for sensitive lecturer actions (session
  activate/close) and QR session creation, so there's a record of who did
  what and when.
- A non-creating verification-attempt lookup was added so the QR verification
  flow can attach to a verification attempt started by geofence, instead of
  creating a duplicate one (see §6).

**Correctness fixes found along the way:**
- QR batch metadata cache TTL was capped, to limit how stale cached QR data
  can be after a session closes.
- The classroom row is now row-locked before an update, closing a race where
  two concurrent classroom edits could silently overwrite each other.

**Test coverage:** every new API module has accompanying service/route tests,
including authorization checks, course-ownership checks, and the manual-review
decision flow.

---

## 5. Wiring the web dashboard to real data

Once the backend APIs existed, the web app's service layer was switched from
mock data to real HTTP calls:

- An authenticated core-backend API client was added to the web app
  (attaches the access token minted from the session's refresh token to every
  request).
- Lecturer mock data → replaced with real core-backend API calls (overview,
  courses, sessions, reports, at-risk students, weekly trend).
- Administrator mock data → replaced with real core-backend API calls (users,
  academic data, classrooms, policies, audit log, institution reports).
- Classroom create/edit form and account activate/deactivate controls were
  wired to their real write endpoints.
- Building options (for the classroom form) are now fetched from the backend
  instead of being hardcoded.
- A "cancelled" session status was added to the UI, now that real session data
  can actually report that state (mock data never had it).
- **Fix:** a Server Component render crash was fixed for the case where the
  refresh-token cookie can't be persisted (e.g. a response already sent) —
  previously this crashed the page instead of degrading gracefully.

At this point, the lecturer and administrator dashboards in the web app are
fully live — no mock data remains in those flows.

---

## 6. Mobile — QR verification auth fix

While reviewing the QR verification path end to end, two related gaps were
found and fixed:

- The QR verification endpoint on the backend didn't require lecturer/student
  authentication and didn't persist a verification attempt — it was closer to
  a stateless "check this code" endpoint than a real verification step.
- The mobile app's QR-scan request wasn't sending an authenticated request at
  all (unlike the geofence check-in request, which was already authenticated).

Both were fixed together: the backend now requires auth on the QR endpoints
and persists the verification attempt (reusing the same
"lock-or-create verification attempt" mechanism used by geofence, via the new
non-creating lookup mentioned in §4), and the mobile app now sends an
authenticated request for QR verification, matching how geofence already
worked. Test coverage was added on both sides.

---

## 7. Product scope change: removed "additional face verification"

Per a direct product decision made mid-project: **students verify their face
only once, at the start of the lecture.** Lecturers are not given the ability
to trigger a second, mid-session face-verification check. This is a
deliberate scope reduction, not a bug fix, and applies to both this branch and
the mobile app going forward.

Concretely, this removed:
- The lecturer-triggered "additional face verification" control from the
  lecturer dashboard.
- The corresponding "additional face-check" policy control from the
  administrator dashboard (since there's no longer a policy to configure).

If you see any reference to a second/repeat face-verification trigger
anywhere in the codebase going forward, it should be treated as a regression
against this decision, not a missing feature.

---

## 8. CI

A GitHub Actions workflow (`.github/workflows/web-ci.yml`) was added for
`apps/web`, running on every PR/push to `main`: TypeScript typecheck, lint,
the Vitest test suite, and a production build. This mirrors the existing
`mobile-ci.yml` convention (Node 24.x, `npm ci` at the repo root, workspace-
scoped script runs).

**Bug found and fixed while setting this up:** `tsc --noEmit` alone fails on a
fresh CI checkout with errors like `Cannot find name 'PageProps'` /
`'LayoutProps'` / `'RouteContext'`. These are ambient types that Next.js
writes into `.next/types/` via its route-typegen step (part of `next build`
or `next dev`) — they don't exist until something generates them. Locally
this was masked because `.next/types` already existed from a previous
`next dev` run; CI's fresh checkout has nothing to generate it. Fixed by
changing the `typecheck` script in `apps/web/package.json` to run Next's
lightweight `next typegen` command before `tsc --noEmit`:

```diff
- "typecheck": "tsc --noEmit",
+ "typegen": "next typegen",
+ "typecheck": "next typegen && tsc --noEmit",
```

Verified by deleting `.next/types` locally and re-running — passes clean,
reproducing the CI environment exactly.

---

## 9. Local end-to-end testing: what broke and how it was fixed

This is the part of the work that doesn't show up as a single clean commit —
it's the result of actually running the full stack (Keycloak, FastAPI
backend, Next.js web app, and the Expo mobile app on a real Android phone
over Wi-Fi, no USB cable) and chasing down every failure that only shows up
under real conditions.

### 9.1 Testing the mobile app over Wi-Fi (no cable)

The mobile app needed to be verified on a physical phone before opening a PR.
Since `adb reverse` (the usual fix for a phone reaching `localhost` services)
requires a USB or wireless-adb connection, the phone and laptop were instead
put on the **same Wi-Fi network**, and every "localhost" reference the phone
would otherwise use was pointed at the laptop's LAN IPv4 address instead:

- Backend started with `--host 0.0.0.0 --port 8000` so it accepts connections
  from other devices on the network, not just the local machine.
- `apps/mobile/.env.local` (a local, gitignored file) was set to use the
  laptop's LAN IP for both `EXPO_PUBLIC_KEYCLOAK_HOST` and
  `EXPO_PUBLIC_CORE_API_URL`, instead of `localhost`.
- Because `EXPO_PUBLIC_*` variables are inlined into the JavaScript bundle at
  Metro bundler start time, changing `.env.local` alone does nothing until
  Metro is restarted (ideally with `--clear`) and the app is reloaded on the
  device — this tripped up testing more than once and is worth remembering.

**A related mistake found and fixed:** `apps/mobile/.env.example` — the
*template* file other developers copy from — had accidentally picked up the
real personal LAN IP address used during this testing, instead of staying a
generic `localhost` placeholder. This was reverted before opening the PR,
since a template file should never contain a real network address tied to one
developer's machine.

### 9.2 Keycloak issuer mismatch → "dashboard could not be loaded"

**Symptom:** after logging in successfully on the phone, the mobile app's
dashboard screen immediately failed with "Dashboard could not be loaded."

**Root cause:** Keycloak stamps every token's `iss` (issuer) claim with
whichever host/address the client actually used to reach it. The phone reaches
Keycloak via the laptop's LAN IP over Wi-Fi, so its tokens carried
`iss: http://<lan-ip>:8080/realms/uniattend`. The backend, however, was only
configured to trust one issuer — `http://localhost:8080/realms/uniattend` —
because that's how the web app (running on the same machine as the backend)
reaches Keycloak. The backend's token verifier does strict issuer validation,
so it correctly rejected the phone's otherwise-valid, correctly-signed token
with `401 Unauthorized`.

This is important to be precise about: **login itself never failed.** The
failure happened one step later, when the dashboard screen made its first
authenticated API call (`GET /api/v1/students/me/attendance-sessions/active`)
to populate the active-session card — that call is what received the 401 and
triggered the dashboard's error state.

**Fix — the backend now accepts more than one trusted issuer:**
- `services/core-backend/core/config.py` — added `keycloak_additional_issuers`
  (a comma-separated env var) and a `keycloak_accepted_issuers` property that
  merges it with the primary `keycloak_expected_issuer`, deduplicated.
- `services/core-backend/modules/identity/auth/token_verifier.py` —
  `KeycloakTokenVerifier` now accepts either a single issuer string or a
  collection of issuers (PyJWT supports both natively via its `issuer=`
  parameter).
- `services/core-backend/modules/identity/auth/dependencies.py` — now passes
  `settings.keycloak_accepted_issuers` (the full set) into the verifier
  instead of just the single primary issuer.
- `services/core-backend/.env(.example)` — documented the new
  `KEYCLOAK_ADDITIONAL_ISSUERS` variable, so both `localhost` (web) and the
  LAN IP (phone) can be trusted at the same time without flipping a single
  config value back and forth between testing sessions.
- New test coverage in `test_config.py` (issuer-set merging/deduplication) and
  `test_auth_token_verifier.py` (a token from any accepted issuer is
  accepted; a token from an issuer outside the set is still rejected).

Confirmed fixed by restarting the backend and watching the live request log —
the phone's subsequent calls to `attendance-sessions/active` and
`students/me/profile` came back `200 OK`, not `401`.

### 9.3 Geofence check-ins returning 409 Conflict

**Symptom:** repeated `409 Conflict` responses from
`POST /attendance-sessions/{id}/geofence-attempts`.

**Important distinction:** a `409` here is *not* "the session doesn't exist"
— that would be a `404`. A `409` means the session exists and is active, but
the request conflicts with existing state.

**Root cause, confirmed by querying the database directly:** the geofence
endpoint always returns `200 OK` with the outcome encoded in the response
body's `decision` field — a `200` does not mean the check-in succeeded. In
this case, the student's location reading was evaluated as **outside the
configured geofence radius** (`OUTSIDE_GEOFENCE`), which is a legitimate
failure. By design, once a session's verification attempt is finalized —
whether it passed or failed — it is **permanently closed**; no further
attempts are accepted for that session. This is intentional, consistent with
the "verify once" rule (§7): repeated check-in attempts against a session that
already resolved (pass or fail) correctly return `409`, not a fresh retry.

**Actual cause of the "outside geofence" reading:** the geofence coordinates
used during testing had been set from the tester's home location, while the
phone doing the check-in was actually on campus — a location mismatch in the
test data/setup, not a bug in the geofence logic itself.

**Fix applied (local dev data only, not a code change):** the affected
verification-attempt rows were reset back to `in_progress` (clearing
`status`, `failure_reason`, `completed_at`) and their prior failed
geofence-attempt history was cleared, so a fresh check-in could be tested
immediately from the correct (campus) location instead of waiting for a new
session to be created.

---

## 10. Known gaps — what's still mock data

Not everything in the mobile app's student dashboard is wired to the backend
yet. Specifically, in
`apps/mobile/src/app/(student)/(tabs)/index.tsx`:

| Dashboard section | Data source | Status |
|---|---|---|
| Active session card / check-in prompt | Real backend (`CoreApiActiveAttendanceSessionService`) | ✅ Live |
| "Good morning, [name]" greeting | `MockProfileService` | ❌ Still mock |
| "My courses" rail | Hardcoded (`dashboardMockData.ts`) | ❌ Still mock |
| "Upcoming attendance" list | `MockDashboardService` | ❌ Still mock |

This is because `DashboardScreen` falls back to mock services whenever
`dashboardService` / `profileService` props aren't explicitly passed in, and
the route that renders it (`index.tsx`) only ever passes the real
`activeSessionService`. The real backend service for profile data already
exists (`CoreApiProfileService`, used elsewhere for the Profile tab) — it
just isn't wired into the dashboard greeting yet. This is a good candidate
for a small, focused follow-up change.

---

## 11. How to verify this branch yourself

Backend tests:
```powershell
cd services/core-backend
python -m pytest
```

Web checks:
```powershell
npm run typecheck --workspace=apps/web
npm run lint --workspace=apps/web
npm run test:ci --workspace=apps/web
npm run build --workspace=apps/web
```

Mobile checks:
```powershell
npm run typecheck --workspace=apps/mobile
npm run test:ci --workspace=apps/mobile
npm run lint --workspace=apps/mobile
```

For manual end-to-end testing (web login, lecturer/admin dashboards, and the
mobile app on a real phone over Wi-Fi), see §9.1 above for the Wi-Fi setup
steps, and the root [README.md](../README.md) for the full local-services
startup sequence (Keycloak, backend, web, mobile).

---

## 12. Merge status

This branch (`feat/web-dashboard-integration`) was checked against the latest
`origin/main` using a non-destructive 3-way merge simulation
(`git merge-tree`) and resolves with **no conflicts**. It is a strict
superset of the earlier `feat/web-dashboard` branch, so that branch does not
need to be merged separately.
