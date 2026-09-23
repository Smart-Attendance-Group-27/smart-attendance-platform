#!/usr/bin/env bash
set -euo pipefail

release_dir=${1:?Pass the absolute release directory}
image_source=${2:-registry}
env_file=/etc/uniattend/private.env
app_compose="$release_dir/deployment/compose.app.yml"
face_compose="$release_dir/deployment/compose.face.yml"

test -r "$env_file"
test -r "$app_compose"
test -r "$face_compose"

app=(docker compose --env-file "$env_file" -f "$app_compose")
face=(docker compose --env-file "$env_file" -f "$face_compose")

wait_healthy() {
  local container=$1 timeout=$2 status
  for ((elapsed=0; elapsed<timeout; elapsed+=5)); do
    status=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container" 2>/dev/null || true)
    if [[ "$status" == healthy ]]; then
      printf '%s healthy\n' "$container"
      return 0
    fi
    if [[ "$status" == unhealthy || "$status" == exited ]]; then
      printf '%s stopped before reaching health\n' "$container" >&2
      return 1
    fi
    sleep 5
  done
  printf '%s health timed out\n' "$container" >&2
  return 1
}

"${app[@]}" config --quiet
"${face[@]}" config --quiet
if [[ "$image_source" == registry ]]; then
  "${app[@]}" pull
  "${face[@]}" pull
elif [[ "$image_source" != local-images ]]; then
  printf 'Image source must be registry or local-images\n' >&2
  exit 2
fi

"${app[@]}" up -d keycloak-db redis
wait_healthy uniattend-app-keycloak-db-1 120
wait_healthy uniattend-app-redis-1 60

"${app[@]}" up -d keycloak
wait_healthy uniattend-app-keycloak-1 300

"${app[@]}" up -d core-api
wait_healthy uniattend-app-core-api-1 180

"${face[@]}" up -d
wait_healthy uniattend-face-face-verification-1 600

"${app[@]}" up -d web
wait_healthy uniattend-app-web-1 180

"${app[@]}" ps
"${face[@]}" ps
