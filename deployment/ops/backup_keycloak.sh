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
day=$(date -u +%Y-%m-%d)
destination="$backup_dir/keycloak-$day.dump.age"
temporary="$destination.tmp"
if [[ -e "$destination" ]]; then
  printf 'Backup already exists for %s\n' "$day"
  exit 0
fi
trap 'rm -f -- "$temporary"' EXIT
docker exec "$container" pg_dump -U keycloak -d keycloak -Fc --no-owner --no-acl \
  | age -r "$(cat "$recipient_file")" -o "$temporary"
test -s "$temporary"
chmod 600 "$temporary"
mv -- "$temporary" "$destination"
printf 'Encrypted Keycloak backup created: %s\n' "$(basename "$destination")"
