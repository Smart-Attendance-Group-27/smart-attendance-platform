#!/usr/bin/env bash
set -euo pipefail
umask 077

release_dir=/opt/uniattend/current
env_file=/etc/uniattend/private.env
recipient_file=/etc/uniattend/backup-recipient.txt
backup_dir=/opt/uniattend/backups
container=uniattend-keycloak-realm-export
compose=(docker compose --env-file "$env_file" -f "$release_dir/deployment/compose.app.yml")

test -r "$recipient_file"
mkdir -p "$backup_dir"
day=$(date -u +%Y-%m-%dT%H%M%SZ)
destination="$backup_dir/keycloak-realm-$day.tar.age"
temporary="$destination.tmp"

cleanup() {
  docker rm -f "$container" >/dev/null 2>&1 || true
  rm -f -- "$temporary"
  "${compose[@]}" start keycloak >/dev/null
}
trap cleanup EXIT

"${compose[@]}" stop keycloak
"${compose[@]}" run --no-deps --name "$container" keycloak \
  export --optimized --realm uniattend --file /tmp/uniattend-realm.json \
  --users same_file
docker cp "$container:/tmp/uniattend-realm.json" - \
  | age -r "$(cat "$recipient_file")" -o "$temporary"
test -s "$temporary"
chmod 600 "$temporary"
mv -- "$temporary" "$destination"
printf 'Encrypted Keycloak realm export created: %s\n' "$(basename "$destination")"
