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
