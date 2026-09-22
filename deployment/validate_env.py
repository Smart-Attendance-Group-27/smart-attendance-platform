"""Validate the first-MVP deployment environment without printing secrets."""

from __future__ import annotations

import argparse
import base64
import binascii
import sys
from pathlib import Path
from urllib.parse import urlparse


REQUIRED = (
    "IMAGE_TAG",
    "CORE_DB_URI",
    "FACE_DB_URI",
    "WEB_BASE_URL",
    "CORE_PUBLIC_BASE_URL",
    "FACE_PUBLIC_BASE_URL",
    "KEYCLOAK_EXPECTED_ISSUER",
    "CORE_KEYCLOAK_JWKS_URL",
    "KEYCLOAK_ADMIN_BASE_URL",
    "KEYCLOAK_ADMIN_REALM",
    "KEYCLOAK_ADMIN_CLIENT_ID",
    "KEYCLOAK_ADMIN_CLIENT_SECRET",
    "WEB_SESSION_SECRET",
    "WEB_KEYCLOAK_ISSUER",
    "WEB_KEYCLOAK_CLIENT_ID",
    "WEB_KEYCLOAK_CLIENT_SECRET",
    "DYNAMIC_QR_HMAC_SECRET",
    "FACE_EMBEDDING_ENCRYPTION_KEY",
    "EXPO_PUBLIC_CORE_API_URL",
    "EXPO_PUBLIC_FACE_VERIFICATION_API_URL",
    "EXPO_PUBLIC_KEYCLOAK_ISSUER_URL",
    "EXPO_PUBLIC_KEYCLOAK_REALM",
    "EXPO_PUBLIC_KEYCLOAK_CLIENT_ID",
)

HTTPS_URLS = (
    "WEB_BASE_URL",
    "CORE_PUBLIC_BASE_URL",
    "FACE_PUBLIC_BASE_URL",
    "KEYCLOAK_EXPECTED_ISSUER",
    "CORE_KEYCLOAK_JWKS_URL",
    "KEYCLOAK_ADMIN_BASE_URL",
    "WEB_KEYCLOAK_ISSUER",
    "EXPO_PUBLIC_CORE_API_URL",
    "EXPO_PUBLIC_FACE_VERIFICATION_API_URL",
    "EXPO_PUBLIC_KEYCLOAK_ISSUER_URL",
)

PLACEHOLDER_MARKERS = (
    "replace-",
    "replace_",
    "example.edu",
    "change-me",
    "changeme",
    "<",
    ">",
)


def parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"Line {line_number} is not KEY=VALUE")
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"Line {line_number} has an empty key")
        values[key] = value.strip().strip('"').strip("'")
    return values


def validate(values: dict[str, str]) -> list[str]:
    errors: list[str] = []

    for key in REQUIRED:
        value = values.get(key, "").strip()
        if not value:
            errors.append(f"{key} is required")
        elif any(marker in value.lower() for marker in PLACEHOLDER_MARKERS):
            errors.append(f"{key} still contains a placeholder")

    for key in HTTPS_URLS:
        value = values.get(key, "")
        if value and urlparse(value).scheme.lower() != "https":
            errors.append(f"{key} must use https")

    for key in ("CORE_DB_URI", "FACE_DB_URI"):
        value = values.get(key, "")
        parsed = urlparse(value)
        if value and parsed.scheme not in {"postgres", "postgresql"}:
            errors.append(f"{key} must be a PostgreSQL URI")
        if value and (not parsed.hostname or not parsed.username):
            errors.append(f"{key} must include a database host and user")

    for key in ("WEB_SESSION_SECRET", "DYNAMIC_QR_HMAC_SECRET"):
        value = values.get(key, "")
        if value and len(value) < 32:
            errors.append(f"{key} must contain at least 32 characters")

    encryption_key = values.get("FACE_EMBEDDING_ENCRYPTION_KEY", "")
    if encryption_key and not any(
        marker in encryption_key.lower() for marker in PLACEHOLDER_MARKERS
    ):
        try:
            decoded = base64.urlsafe_b64decode(encryption_key.encode("ascii"))
        except (UnicodeEncodeError, binascii.Error, ValueError):
            errors.append("FACE_EMBEDDING_ENCRYPTION_KEY must be URL-safe base64")
        else:
            if len(decoded) != 32:
                errors.append(
                    "FACE_EMBEDDING_ENCRYPTION_KEY must decode to exactly 32 bytes"
                )

    if values.get("EXPO_PUBLIC_CORE_API_URL") != values.get("CORE_PUBLIC_BASE_URL"):
        errors.append(
            "EXPO_PUBLIC_CORE_API_URL must match CORE_PUBLIC_BASE_URL for this release"
        )
    if values.get("EXPO_PUBLIC_FACE_VERIFICATION_API_URL") != values.get(
        "FACE_PUBLIC_BASE_URL"
    ):
        errors.append(
            "EXPO_PUBLIC_FACE_VERIFICATION_API_URL must match FACE_PUBLIC_BASE_URL"
        )
    if values.get("EXPO_PUBLIC_KEYCLOAK_ISSUER_URL") != values.get(
        "KEYCLOAK_EXPECTED_ISSUER"
    ):
        errors.append(
            "EXPO_PUBLIC_KEYCLOAK_ISSUER_URL must match KEYCLOAK_EXPECTED_ISSUER"
        )
    if values.get("WEB_KEYCLOAK_ISSUER") != values.get(
        "KEYCLOAK_EXPECTED_ISSUER"
    ):
        errors.append(
            "WEB_KEYCLOAK_ISSUER must match KEYCLOAK_EXPECTED_ISSUER for this release"
        )

    for key in ("PUSH_WORKER_ENABLED", "REMINDER_SCHEDULER_ENABLED"):
        value = values.get(key, "").lower()
        if value not in {"true", "false"}:
            errors.append(f"{key} must be true or false")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate an UniAttend MVP deployment environment file."
    )
    parser.add_argument(
        "env_file",
        nargs="?",
        type=Path,
        default=Path("deployment/mvp.env"),
    )
    arguments = parser.parse_args()

    try:
        values = parse_env(arguments.env_file)
    except (OSError, ValueError) as error:
        print(f"Environment validation failed: {error}", file=sys.stderr)
        return 1

    errors = validate(values)
    if errors:
        print("Environment validation failed:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    print(
        f"Environment validation passed for {len(values)} configured variables."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
