# VPS application database migration

**Owner:** Manushan

**Completed:** 2026-09-27

**Status:** Cut over and verified

## Result

Core and Face Verification now use a dedicated PostgreSQL 17 container on the
netcup VPS. Keycloak continues to use its separate PostgreSQL database. The
managed Supabase database was not modified or deleted and remains available as
the rollback source.

The application database is isolated on the internal
`uniattend-application-data` Docker network. It has no host or public port. Its
initial limits are 1 GiB RAM, 0.75 CPU and 30 PostgreSQL connections. Core and
Face retain pools of at most five connections each.

## Migration verification

The final write-frozen export and restored database matched across:

- all 44 application tables using exact row counts and order-independent row
  content hashes;
- 411 column definitions;
- 152 constraint names;
- 96 index names;
- all identity links, classrooms, sessions, notification records and device
  tokens;
- all four encrypted face profiles.

The Face service decrypted all four copied embeddings with the existing key.
Each has 512 dimensions and uses the `buffalo_l` model version 1. The MVP
schema gate passed with an active verification threshold and four generated
reference faces.

The pilot student account completed a fresh Keycloak PKCE login and
Core identity lookup after cutover. Public Web, Core, Face database and
Keycloak discovery health checks all returned HTTP 200.

The administrator institution-report repository previously took about 2,161
ms at its median over the Europe-to-Seoul connection. After cutover, 20 runs
had a 10.10 ms median, 8.14 ms minimum and 28.06 ms maximum. A pooled
`SELECT 1` had a 0.40 ms median.

## Credentials and rollback

Login passwords did not change because Keycloak and its database did not
change. Application UUIDs and Keycloak subject mappings were copied exactly.
The face embedding encryption key also remained unchanged.

The original protected environment file is retained on the VPS as a mode-0600
rollback file. To roll back, stop Core and Face, reconcile or explicitly
discard writes created after cutover, restore the Supabase database URI and
TLS mode from that file, then recreate Core and Face with the release Compose
files. Supabase must remain unchanged until Manushan accepts the local database
and its backup cycle.

## Backup operation

The application database is dumped daily at 03:00 UTC, encrypted to the same
off-host age recipient used by Keycloak, and retained on the VPS for 30 days.
Run `deployment/ops/pull_application_db_backups.ps1` from the protected
administrator workstation to copy and SHA-256 verify the encrypted archives.
The age private key must remain off the VPS.

An encrypted post-cutover archive was copied and checksum-verified off the VPS.
It was decrypted into an isolated temporary PostgreSQL cluster and restored
with all 44 application tables and four face profiles before this migration
was declared complete.
