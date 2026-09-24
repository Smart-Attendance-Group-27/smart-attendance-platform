#!/usr/bin/env bash
set -euo pipefail
umask 077

release_dir=/opt/uniattend/current
env_file=/etc/uniattend/private.env
recipient_file=/etc/uniattend/backup-recipient.txt
backup_dir=/opt/uniattend/backups
test -r "$recipient_file"
test -r "$env_file"
mkdir -p "$backup_dir"

container=$(docker compose --env-file "$env_file" -f "$release_dir/deployment/compose.app.yml" ps -q keycloak-db)
test -n "$container"
stamp=$(date -u +%Y-%m-%dT%H%M%SZ)
destination="$backup_dir/keycloak-$stamp.dump.age"
temporary="$destination.tmp"
if [[ -e "$destination" ]]; then
  printf 'Backup already exists for %s\n' "$stamp" >&2
  exit 1
fi
trap 'rm -f -- "$temporary"' EXIT
docker exec "$container" pg_dump -U keycloak -d keycloak -Fc --no-owner --no-acl \
  | age -r "$(cat "$recipient_file")" -o "$temporary"
test -s "$temporary"
chmod 600 "$temporary"
mv -- "$temporary" "$destination"
printf 'Encrypted Keycloak backup created: %s\n' "$(basename "$destination")"

# Keep a bounded local recovery window. Copy and verify archives off the VPS
# regularly; this cleanup affects only dated Keycloak database dumps here.
find "$backup_dir" -maxdepth 1 -type f -name 'keycloak-*.dump.age' \
  -mtime +30 -print -delete
