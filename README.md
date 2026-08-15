# Smart Attendance Platform

University attendance platform with student mobile check-in, Keycloak login,
FastAPI backend services, and QR-based attendance verification.

This README explains how to run the project locally up to the current QR
verification flow:

```text
Keycloak login
FastAPI core backend
Next.js web QR test page
Expo mobile app on a real Android phone
```

## Project Structure

```text
smart-attendance-platform/
|-- apps/
|   |-- mobile/            Expo React Native student app
|   `-- web/               Next.js / Vercel QR test web app
|-- services/
|   `-- core-backend/      FastAPI core API
|-- infra/
|   `-- local/keycloak/    Local Keycloak Docker setup
`-- database/              Database schema and seed files
```

## Prerequisites

Install these first:

- Node.js and npm
- Python 3.12+
- Docker Desktop
- Android Studio / Android platform tools
- A real Android phone with USB debugging enabled

Install JavaScript dependencies from the repository root:

```powershell
npm install
```

## 1. Start Local Keycloak

Keycloak handles login for the mobile app.

From the repository root:

```powershell
docker compose --env-file infra/local/keycloak/.env.example -f infra/local/keycloak/docker-compose.yml up -d
```

Check that the containers are running:

```powershell
docker compose --env-file infra/local/keycloak/.env.example -f infra/local/keycloak/docker-compose.yml ps
```

Verify the imported `uniattend` realm:

```powershell
curl.exe -I http://localhost:8080/realms/uniattend
```

Expected:

```text
HTTP/1.1 200 OK
```

Keycloak admin console:

```text
http://localhost:8080/admin
```

Default local credentials:

```text
Username: admin
Password: admin
```

## 2. Start the FastAPI Core Backend

The backend creates QR sessions and verifies scanned QR codes.

Create `services/core-backend/.env` from:

```text
services/core-backend/.env.example
```

Fill in the required database values, including Supabase/PostgreSQL credentials.

Install Python dependencies:

```powershell
cd services/core-backend
python -m pip install -r requirements.txt
```

For USB phone testing with `adb reverse`, run the backend on localhost:

```powershell
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

For LAN/Wi-Fi phone testing, expose the backend to your local network instead:

```powershell
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Check from your laptop:

```powershell
curl.exe http://localhost:8000/health
curl.exe http://localhost:8000/health/db
```

If you use the LAN/Wi-Fi method, find your laptop IPv4 address:

```powershell
ipconfig
```

Then from your phone browser, open:

```text
http://YOUR_LAPTOP_IP:8000/health
```

Example:

```text
http://192.168.1.5:8000/health
```

If the phone cannot open this URL:

- make sure phone and laptop are on the same Wi-Fi
- make sure VPN/mobile data is not interfering
- allow Python/Uvicorn through Windows Defender Firewall for private networks
- confirm FastAPI was started with `--host 0.0.0.0`

## 3. Run the Vercel / Next.js Web QR Test App

The web app is a Next.js app intended for Vercel deployment later. For local
development, run it with the Next.js dev server. It is currently used as the
lecturer-side QR test screen.

From the repository root:

```powershell
npm.cmd run dev --workspace=apps/web
```

Open:

```text
http://localhost:3000/qr-test
```

Use this development attendance session ID:

```text
40000000-0000-0000-0000-000000000001
```

Click `Create QR session`.

The page calls the FastAPI backend and displays a QR code. The QR code contains:

```json
{
  "qrSessionId": "...",
  "qrValue": "..."
}
```

The mobile scanner uses `qrSessionId` in the URL path and sends `qrValue` in the
request body to verify the scan.

The web app defaults to:

```text
CORE_BACKEND_URL=http://127.0.0.1:8000
```

If needed, create `apps/web/.env.local`:

```text
CORE_BACKEND_URL=http://127.0.0.1:8000
```

## 4. Configure Mobile for a Real Android Phone

The Android emulator can use `10.0.2.2`. For a real Android phone, use one of
these methods.

### Method 1: USB forwarding with `adb reverse` (recommended)

Use this when the phone is connected by USB with USB debugging enabled. This
avoids changing IP addresses and avoids Windows firewall/LAN issues.

Run:

```powershell
adb reverse tcp:8000 tcp:8000
adb reverse tcp:8080 tcp:8080
```

Check active reverse rules:

```powershell
adb reverse --list
```

Expected entries:

```text
tcp:8000 tcp:8000
tcp:8080 tcp:8080
```

Create or update:

```text
apps/mobile/.env
```

Use:

```text
EXPO_PUBLIC_KEYCLOAK_HOST=127.0.0.1
EXPO_PUBLIC_CORE_API_URL=http://127.0.0.1:8000
```

With this method, start FastAPI on localhost:

```powershell
cd services/core-backend
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

Important notes:

- This only works while the phone is connected by USB.
- If you unplug or reconnect the phone, run the `adb reverse` commands again.
- This is Android only, not iPhone.
- You do not need Windows firewall/LAN IP access for backend/mobile testing
  through USB.

### Method 2: LAN/Wi-Fi IP address

Create or update:

```text
apps/mobile/.env
```

Example:

```text
EXPO_PUBLIC_KEYCLOAK_HOST=192.168.1.5
EXPO_PUBLIC_CORE_API_URL=http://192.168.1.5:8000
```

Replace `192.168.1.5` with your laptop IPv4 address from `ipconfig`.

Before starting the mobile app, verify these URLs from the phone browser:

```text
http://YOUR_LAPTOP_IP:8080/realms/uniattend
http://YOUR_LAPTOP_IP:8000/health
```

Both must work from the phone.

Use this method if you want the phone and laptop to communicate through Wi-Fi
instead of USB.

## 5. Run / Restart the Mobile App on a Real Phone

Connect the phone by USB and enable USB debugging.

Install or rebuild the Android dev client:

```powershell
cd apps/mobile
npx.cmd expo run:android --device
```

Start Expo with the dev client:

```powershell
npx.cmd expo start --dev-client --clear
```

Then fully close and reopen the installed UniAttend app on the phone.

Do not use Expo Go for this project because the app uses native modules such as:

- `expo-camera`
- `expo-crypto`
- `expo-secure-store`
- `expo-dev-client`

If native module errors appear, uninstall the app from the phone and rebuild:

```powershell
adb uninstall com.group27.uniattend
npx.cmd expo run:android --device
```

## Current QR Verification Flow

1. Start Keycloak.
2. Start FastAPI backend:
   - USB method: `--host 127.0.0.1 --port 8000`
   - LAN method: `--host 0.0.0.0 --port 8000`
3. Start the web app.
4. Open `http://localhost:3000/qr-test`.
5. Generate a QR session for:

```text
40000000-0000-0000-0000-000000000001
```

6. Open the mobile app on the real phone.
7. Complete the mock flow until the QR scanner screen.
8. Scan the QR from the web page.
9. The mobile app calls:

```http
POST /api/v1/qr-sessions/{qrSessionId}/verify
```

with:

```json
{
  "qrValue": "scanned-raw-qr-value"
}
```

The screen shows one of:

```text
QR verified
Invalid QR code
QR code expired
QR session closed
Connection / verification error
```

The raw QR value is not shown in the mobile UI.

## Useful Validation Commands

From the repository root:

```powershell
npm.cmd run typecheck --workspace=apps/mobile
npm.cmd run test:ci --workspace=apps/mobile
npm.cmd run lint --workspace=apps/mobile
npm.cmd run lint --workspace=apps/web
npm.cmd run build --workspace=apps/web
```

From `services/core-backend`:

```powershell
python -m pytest tests
```

## Stop Local Services

Stop Keycloak:

```powershell
docker compose --env-file infra/local/keycloak/.env.example -f infra/local/keycloak/docker-compose.yml down
```

Stop FastAPI, Expo, and Next.js by pressing:

```text
Ctrl+C
```

in their terminal windows.
