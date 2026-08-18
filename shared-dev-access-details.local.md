# UniAttend Shared Development Access Details

Private local file. Do not commit or share publicly.

Use this as the team handover sheet for shared Keycloak, mock users, Docker URLs,
mobile URLs, and local development access. Fill the missing password/owner fields
manually.

## Shared Keycloak

Keycloak base URL: https://keycloak-production-be79.up.railway.app
Realm: Uni Attend
Realm issuer URL: https://keycloak-production-be79.up.railway.app/realms/Uni%20Attend
Admin console: https://keycloak-production-be79.up.railway.app/admin

Main Keycloak admin:

Username: admin
Password: helloworld
Owner/contact: TODO_FILL

Mobile client:
Client ID: uniattend-mobile
Redirect scheme: uniattend
Required token realm role for students: student

Web client:

Client ID: uniattend-web
Client secret: TODO_FILL_IF_REQUIRED
Required token realm role for lecturers: lecturer
Required token realm role for admins: administrator

Core API expected issuer:

```text
KEYCLOAK_EXPECTED_ISSUER=https://keycloak-production-be79.up.railway.app/realms/Uni%20Attend
CORE_KEYCLOAK_JWKS_URL=https://keycloak-production-be79.up.railway.app/realms/Uni%20Attend/protocol/openid-connect/certs
KEYCLOAK_AUTHORIZED_CLIENTS=uniattend-mobile,uniattend-web
```

## Mock Student Accounts

### Student 1

```text
Username: 230736r
Password: student
Email: 230736r@student.uniattend.test
Keycloak user ID: 659a6da3-e6ab-4740-9ea3-2212948b9f27
Name: Manushan Hasanka
Registration number: 230736R
Required Keycloak realm role: student
```

### Student 2

```text
Username: 230737r
Password: student
Email: 230737r@student.uniattend.test
Keycloak user ID: 8fb03922-5c9c-4734-a823-e3f4932925eb
Name: Anura Kumara
Registration number: 230737R
Required Keycloak realm role: student
```

## Mock Lecturer Accounts

### Lecturer 1

```text
Username: lectuere01
Password: lecturer
Email: lecutere01@lectuere.uniattend.test
Keycloak user ID: 325e2cdd-71b6-417e-bb6e-3c990ac7aace
Name: Indika Perera
Employee number: lecturer01
Required Keycloak realm role: lecturer
```

### Lecturer 2

```text
Username: lectuere02
Password: lecturer
Email: lecutere02@lectuere.uniattend.test
Keycloak user ID: 22bd9602-6061-4869-9766-83f7ec03b24a
Name: Dulani Meedeniya
Employee number: lecturer02
Required Keycloak realm role: lecturer
```

## Mock Admin Account

```text
Username: admin01
Password: admin
Email: admin01@lectuere.uniattend.test
Keycloak user ID: e66d4bf5-ed74-4f55-8ca8-6754199605db
Name: Kamal Perera
Required Keycloak realm role: administrator
```

## Local Docker URLs

```text
Web dashboard: http://localhost:3000
Core API: http://localhost:8000
Core API health: http://localhost:8000/health
Face verification API: http://localhost:8001
Face verification health: http://localhost:8001/health
Redis: localhost:6379
Local Docker Keycloak fallback: http://localhost:8080
Local Keycloak DB: localhost:5433
```

## Physical Android Phone Testing Through USB

Mobile app local env:

```text
EXPO_PUBLIC_CORE_API_URL=http://127.0.0.1:8000
EXPO_PUBLIC_FACE_VERIFICATION_API_URL=http://127.0.0.1:8001
EXPO_PUBLIC_KEYCLOAK_ISSUER_URL=https://keycloak-production-be79.up.railway.app/realms/Uni%20Attend
EXPO_PUBLIC_KEYCLOAK_CLIENT_ID=uniattend-mobile
```

## Required Local Secrets To Fill

Root `.env`:

```text
CORE_DB_HOST=TODO_FILL
CORE_DB_USER=TODO_FILL
CORE_DB_PASSWORD=TODO_FILL
WEB_SESSION_SECRET=TODO_FILL
WEB_KEYCLOAK_CLIENT_SECRET=TODO_FILL
DYNAMIC_QR_HMAC_SECRET=TODO_FILL
FACE_EMBEDDING_ENCRYPTION_KEY=TODO_FILL
KEYCLOAK_ADMIN_USERNAME=TODO_FILL_FOR_LOCAL_KEYCLOAK_ONLY
KEYCLOAK_ADMIN_PASSWORD=TODO_FILL_FOR_LOCAL_KEYCLOAK_ONLY
KEYCLOAK_DB_PASSWORD=TODO_FILL_FOR_LOCAL_KEYCLOAK_ONLY
```
