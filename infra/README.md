# Local Infrastructure

UniAttend keeps local infrastructure in separate Compose projects so service
ownership remains clear:

- [`local/keycloak`](local/keycloak/README.md) runs Keycloak and its private
  PostgreSQL database for authentication data.
- [`local/application-db`](local/application-db/README.md) runs the UniAttend
  application PostgreSQL database, applies the canonical schema and migrations,
  and adds local geofence demonstration sessions.

Start and stop each project with the commands in its README. Neither local
project connects to Supabase.
