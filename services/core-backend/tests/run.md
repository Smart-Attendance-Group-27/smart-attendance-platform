backend

cd services/core-backend
.\.venv\Scripts\python.exe -m pytest

//only geofencing files
.\.venv\Scripts\python.exe -m pytest -k geofence -v

mobile
from repo root
npm run test:ci --workspace=apps/mobile

//just the location feature

npm run test --workspace=apps/mobile -- src/features/location
