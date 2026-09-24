#!/usr/bin/env bash
set -euo pipefail
umask 077

release_dir=${1:?Pass the absolute release directory}
ghcr_user=${2:?Pass the GitHub username for the read-only package token}
test -r "$release_dir/deployment/ops/deploy_private.sh"

auth_dir=$(mktemp -d /tmp/uniattend-ghcr.XXXXXXXX)
cleanup() {
  docker logout ghcr.io >/dev/null 2>&1 || true
  rm -f -- "$auth_dir/config.json"
  rmdir -- "$auth_dir"
}
trap cleanup EXIT
export DOCKER_CONFIG="$auth_dir"

# The token arrives only on stdin. Docker's temporary config is removed when
# deployment finishes; no package credential is retained on the VPS.
docker login ghcr.io -u "$ghcr_user" --password-stdin >/dev/null
"$release_dir/deployment/ops/deploy_private.sh" "$release_dir"
