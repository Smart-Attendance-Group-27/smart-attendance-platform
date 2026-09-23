"""Generate the first tunnel-only VPS configuration from an existing local env.

Run this on a trusted workstation. Copy the resulting file over SSH and remove
the local copy after it is installed under /etc/uniattend on the VPS.
"""

from __future__ import annotations

import argparse
import os
import secrets
from pathlib import Path
from urllib.parse import urlparse

from render_realm import parse_env


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-env", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--image-tag", required=True)
    args = parser.parse_args()

    source = parse_env(args.source_env)
    db_uri = source.get("CORE_DB_URI", "")
    face_key = source.get("FACE_EMBEDDING_ENCRYPTION_KEY", "")
    parsed = urlparse(db_uri)
    if parsed.scheme not in {"postgres", "postgresql"} or not parsed.hostname:
        raise ValueError("Source CORE_DB_URI is not a PostgreSQL URI")
    if not parsed.hostname.endswith(".supabase.com"):
        raise ValueError("Source database is not the expected Supabase pooler")
    if not face_key:
        raise ValueError("Existing face embedding key is required")
    if len(args.image_tag) != 40 or any(char not in "0123456789abcdef" for char in args.image_tag):
        raise ValueError("Image tag must be a full lowercase Git commit SHA")

    values = {
        "DEPLOY_IMAGE_PREFIX": "ghcr.io/smart-attendance-group-27/smart-attendance-platform",
        "IMAGE_TAG": args.image_tag,
        "CORE_DB_URI": db_uri,
        "FACE_DB_URI": db_uri,
        "FACE_EMBEDDING_ENCRYPTION_KEY": face_key,
        "KEYCLOAK_DB_PASSWORD": secrets.token_urlsafe(48),
        "KEYCLOAK_ADMIN_USERNAME": "admin",
        "KEYCLOAK_ADMIN_PASSWORD": secrets.token_urlsafe(48),
        "KEYCLOAK_ADMIN_CLIENT_SECRET": secrets.token_urlsafe(48),
        "WEB_KEYCLOAK_CLIENT_SECRET": secrets.token_urlsafe(48),
        "WEB_SESSION_SECRET": secrets.token_urlsafe(48),
        "DYNAMIC_QR_HMAC_SECRET": secrets.token_urlsafe(48),
        "WEB_BASE_URL": "https://app.152-53-33-198.sslip.io",
        "KEYCLOAK_PUBLIC_URL": "https://auth.152-53-33-198.sslip.io",
        "KEYCLOAK_EXPECTED_ISSUER": "https://auth.152-53-33-198.sslip.io/realms/uniattend",
        "KEYCLOAK_REALM_FILE": "/etc/uniattend/realm.json",
    }
    if any("\n" in value or "'" in value for value in values.values()):
        raise ValueError("A configuration value cannot be serialized safely")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(args.out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as output:
        for key, value in values.items():
            output.write(f"{key}='{value}'\n")
    print("Private environment prepared with restricted permissions.")


if __name__ == "__main__":
    main()
