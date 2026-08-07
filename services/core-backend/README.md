# Core Backend

FastAPI backend service for the smart attendance platform.

## Setup

1. Create `services/core-backend/.env` from `.env.example`.
2. Fill in the Supabase database credentials and `TOKEN_SECRET`.
3. Install dependencies:

```powershell
cd services/core-backend
python -m pip install -r requirements.txt
```

4. Run the API:

```powershell
python -m uvicorn main:app --reload
```

## Health checks

- `GET /health` verifies the API process is running.
- `GET /health/db` verifies the API can connect to PostgreSQL.

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
