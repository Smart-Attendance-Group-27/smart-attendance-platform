#!/usr/bin/env bash
set -euo pipefail
umask 077

release_dir=/opt/uniattend/current
database_env_file=/etc/uniattend/application-db.env
recipient_file=/etc/uniattend/backup-recipient.txt
backup_dir=/opt/uniattend/backups
compose_file="$release_dir/deployment/compose.database.yml"

test -r "$database_env_file"
test -r "$recipient_file"
test -r "$compose_file"
mkdir -p "$backup_dir"

container=$(docker compose --env-file "$database_env_file" -f "$compose_file" ps -q application-db)
test -n "$container"
stamp=$(date -u +%Y-%m-%dT%H%M%SZ)
destination="$backup_dir/application-$stamp.dump.age"
temporary="$destination.tmp"
if [[ -e "$destination" ]]; then
  printf 'Backup already exists for %s\n' "$stamp" >&2
  exit 1
fi

trap 'rm -f -- "$temporary"' EXIT
docker exec "$container" sh -c \
  'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc --no-owner --no-acl' \
  | age -r "$(cat "$recipient_file")" -o "$temporary"
test -s "$temporary"
chmod 600 "$temporary"
mv -- "$temporary" "$destination"
printf 'Encrypted application database backup created: %s\n' "$(basename "$destination")"

find "$backup_dir" -maxdepth 1 -type f -name 'application-*.dump.age' \
  -mtime +30 -print -delete
