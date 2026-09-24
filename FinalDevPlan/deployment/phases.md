Proposed first deployment process
I will use the following phased approach. No deployment changes will begin until you approve it.
## Phase 1 — Establish the release baseline
1. Fetch the latest main, including all recently merged team PRs.
2. Review the final combined state for conflicts, incomplete migrations and changed environment variables.
3. Create a dedicated branch:
deployment/first-vps-release
4. Record the exact release commit so the deployed version is reproducible.
5. Run the complete repository CI and local production build before changing the VPS.
## Phase 2 — Create the production runtime
The VPS will use separate Docker services:
Reverse proxy
├── Next.js Web
├── Core API
├── Keycloak
├── Keycloak PostgreSQL
├── Redis
└── Face Verification
Face Verification will have:
- Its own container image
- Its own Compose project
- One Uvicorn worker
- FACE_MAX_CONCURRENT_INFERENCES=1
- 2 GiB memory limit
- Dedicated model-cache volume
- Internal communication with Core through a shared private Docker network
- No publicly exposed container port
This retains the boundary required to replicate it or move it to another server later.
## Phase 3 — Prepare production configuration
I will build deployment-specific environment files from the existing environments.
This includes:
- Supabase pooled database connection
- Keycloak production URLs and realm configuration
- Core and Face database pools
- Redis configuration
- Internal service URLs
- Authentication issuer and audience
- CORS and trusted origins
- Web Backend-for-Frontend URLs
- Face embedding encryption key
- Internal service credentials
- File-size and request limits
Deployment secrets will be stored under:
/etc/uniattend/
They will have restricted permissions and will never be committed to Git or printed in logs.
Development secrets will not be copied blindly. I will retain valid shared-service credentials and generate new VPS-specific passwords where appropriate.
## Phase 4 — Build and publish immutable images
GitHub Actions will build versioned images for:
- Web
- Core Backend
- Face Verification
- Production Keycloak
Images will be tagged with the Git commit SHA and published to GitHub Container Registry.
The VPS will deploy exact image tags instead of building the project directly on the server. This provides repeatable deployments and simple rollbacks.
## Phase 5 — Prepare data safely
Supabase
1. Test the connection from the VPS.
2. Measure Europe-to-Seoul latency.
3. Verify SSL and connection-pool settings.
4. Inspect the migration history.
5. Create or verify a recovery point.
6. Run only pending migrations through a one-off controlled job.
7. Run the schema verification script.
Keycloak
1. Create a dedicated PostgreSQL volume and database.
2. Use an optimized Keycloak production image.
3. Import or migrate the existing realm.
4. Verify clients, roles, redirect URIs and service accounts.
5. Export a recoverable realm copy after validation.
No schema migration will run automatically merely because a container starts.
## Phase 6 — Deploy privately first
Before opening web traffic:
1. Start Keycloak PostgreSQL and Redis.
2. Start Keycloak and verify internal readiness.
3. Start Core and verify Supabase, Redis and Keycloak connectivity.
4. Start Face Verification and allow buffalo_l to load.
5. Confirm its model cache and runtime memory.
6. Start the Next.js web service.
7. Keep public ports 80 and 443 closed.
8. Test services through SSH tunnels and server-side health checks.
This stage proves the deployment without exposing an incomplete configuration publicly.
## Phase 7 — Validate the system
I will test:
- Container health and restart behavior
- Keycloak login and token issuance
- Core token validation
- Web session handling
- Supabase queries and migration state
- Redis connectivity
- Face service health and model readiness
- Reference embedding retrieval
- Controlled face inference
- Core-to-Face internal communication
- Memory, CPU and disk consumption
- Log redaction
- Container recovery after an intentional restart
The Face model will load once per container startup and remain available for subsequent requests.
## Phase 8 — Initial IP-only access
Without a domain, testing will use SSH tunnels:
Local computer → encrypted SSH tunnel → private VPS services
This supports administrator testing without transmitting credentials or student photos over public HTTP.
Keycloak and browser authentication are sensitive to stable public hostnames. IP-only testing will therefore focus on internal health, APIs and controlled authentication checks. Public mobile and browser acceptance comes after the domain is connected.
## Phase 9 — Domain and HTTPS cutover
When a domain is available:
1. Create app, api, auth and face DNS records.
2. Open ports 80 and 443.
3. Configure Caddy and trusted HTTPS certificates.
4. Update Keycloak’s external hostname and redirect URIs.
5. Update web, Core, CORS and mobile public URLs.
6. Expose only approved routes.
7. Block Face /internal/* routes at the reverse proxy.
8. Run complete browser and physical-device authentication tests.
Cloudflare can manage DNS and optionally proxy the traffic. Cloudflare R2 remains independent from this step.
## Phase 10 — Backups and monitoring
I will configure:
- Daily encrypted Keycloak pg_dump
- Keycloak realm export procedure
- Docker health checks
- Container log rotation
- Disk, memory and CPU checks
- External uptime monitoring after the domain exists
- A documented restore test
- Release rollback commands
- A two-month shutdown and data-export procedure
## Phase 11 — PR and release completion
1. Commit deployment code to deployment/first-vps-release.
2. Open a PR using the project convention.
3. Monitor and repair CI failures.
4. Merge only after checks pass.
5. Deploy the merged commit SHA.
6. Run post-deployment smoke tests.
7. Record the deployed versions, configuration decisions and measured resource usage.
Scope decisions
Liveness
Your earlier instruction was to proceed while liveness is still under development. Recent merged code appears to enable liveness enforcement, so I will audit the effective configuration and keep incomplete liveness enforcement disabled for the first pilot unless you explicitly change that decision.
Face Verification
The service will be deployed and tested, but attendance enforcement will only be enabled after its physical-device flow passes. Enrollment and readiness can be tested independently.
Cloudflare R2
R2 integration is currently missing from the enrollment code. Implementing its storage adapter is a product change rather than a server configuration task.
It will not block the first deployment. I recommend deploying the current enrollment mechanism first, then implementing R2 through a separate reviewed PR. Raw attendance captures will not be persisted.