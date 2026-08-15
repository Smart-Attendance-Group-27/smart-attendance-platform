# Core Backend

FastAPI backend service for the smart attendance platform.

## Setup

1. Create `services/core-backend/.env` from `.env.example`.
2. Fill in the Supabase database connection and the Keycloak settings.
   `DB_URI` takes precedence: when it is set, the individual `DB_HOST`,
   `DB_PORT`, `DB_NAME`, `DB_USER` and `DB_PASSWORD` values are ignored. Use one
   style, not both. `TOKEN_SECRET` is deprecated and may stay empty.
3. Install dependencies (Python 3.11-3.13 from python.org; the MSYS2 build
   cannot install `pydantic-core`):

```powershell
cd services/core-backend
python -m pip install -r requirements.txt
```

4. Run the API:

```powershell
python -m uvicorn main:app --reload
```

5. Run the tests:

```powershell
python -m pytest
```

Never commit `.env`, and never paste the connection URI into logs or tickets.

## Health checks

- `GET /health` verifies the API process is running.
- `GET /health/db` verifies the API can connect to PostgreSQL.

## Authenticated endpoints

Both require `Authorization: Bearer <keycloak-access-token>`.

```http
GET /api/v1/me
GET /api/v1/students/me/profile
```

The token is validated against Keycloak's JWKS: RS256 only, live expiry, an
exactly matching issuer and the `uniattend-api` audience. The verified `sub`
claim is then resolved through `identity.users.keycloak_user_id` to the internal
`identity.users.id`, which stays the permanent application user ID. The backend
never queries Keycloak's own database.

| Situation | Status |
| --- | ---: |
| Missing, malformed, invalid, expired, wrong-issuer or wrong-audience token | 401 |
| Keycloak user not linked to an application user | 404 |
| Application account not active | 403 |
| Non-student requesting the student profile | 403 |
| Student profile missing or not active | 404 |
| Valid linked active student | 200 |
| Keycloak settings absent from `.env` | 503 |

`GET /api/v1/students/me/profile` takes no identifier from the request; the
student is derived from the token.

## Full setup and manual testing

See [docs/backend/integration-and-manual-testing.md](../../docs/backend/integration-and-manual-testing.md).

## Static QR session creation

Create a static QR verification token for an active attendance session:

```http
POST /api/v1/attendance-sessions/{session_id}/qr-sessions
```

Optional request body:

```json
{
  "validForSeconds": 300
}
```

Development seed session:

```text
40000000-0000-0000-0000-000000000001
```

Example Postman URL:

```text
http://127.0.0.1:8000/api/v1/attendance-sessions/40000000-0000-0000-0000-000000000001/qr-sessions
```

The response includes `qrValue` once. The raw value is not stored in the database.

Safe database checks after a manual request:

```sql
SELECT id, session_id, status, activated_at, deactivated_at
FROM attendance_session.qr_token_batches
WHERE session_id = '40000000-0000-0000-0000-000000000001'
ORDER BY created_at DESC;

SELECT qr_batch_id, sequence_number, valid_from, expires_at, revoked_at, length(token_hash) AS token_hash_length
FROM attendance_session.qr_tokens
ORDER BY created_at DESC
LIMIT 5;
```

Do not select or log secret environment values. The database stores only the SHA-256 token hash.
