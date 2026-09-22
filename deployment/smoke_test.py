"""Smoke-test the public MVP endpoints after deployment."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

from validate_env import parse_env


def request_json(url: str, timeout_seconds: float) -> tuple[int, object]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "uniattend-mvp-smoke-test/1"},
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        body = response.read()
        return response.status, json.loads(body) if body else None


def request_status(url: str, timeout_seconds: float) -> int:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "uniattend-mvp-smoke-test/1"},
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        response.read(1)
        return response.status


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check UniAttend web, API, face, DB, and Keycloak endpoints."
    )
    parser.add_argument(
        "env_file",
        nargs="?",
        type=Path,
        default=Path("deployment/mvp.env"),
    )
    parser.add_argument("--timeout", type=float, default=10.0)
    arguments = parser.parse_args()

    try:
        values = parse_env(arguments.env_file)
    except (OSError, ValueError) as error:
        print(f"Smoke test could not read the environment: {error}", file=sys.stderr)
        return 1

    web_url = values.get("WEB_BASE_URL", "").rstrip("/")
    core_url = values.get("CORE_PUBLIC_BASE_URL", "").rstrip("/")
    face_url = values.get("FACE_PUBLIC_BASE_URL", "").rstrip("/")
    issuer_url = values.get("KEYCLOAK_EXPECTED_ISSUER", "").rstrip("/")

    checks = (
        ("web", f"{web_url}/", "status"),
        ("core process", f"{core_url}/health", "json"),
        ("core database", f"{core_url}/health/db", "json"),
        ("face process/model", f"{face_url}/health", "json"),
        ("face database", f"{face_url}/health/db", "json"),
        (
            "Keycloak discovery",
            f"{issuer_url}/.well-known/openid-configuration",
            "json",
        ),
    )

    failures = 0
    for name, url, response_type in checks:
        try:
            if response_type == "json":
                status, payload = request_json(url, arguments.timeout)
                healthy = status == 200 and isinstance(payload, dict)
            else:
                status = request_status(url, arguments.timeout)
                healthy = 200 <= status < 400
        except (OSError, ValueError, urllib.error.HTTPError) as error:
            print(f"FAIL {name}: {type(error).__name__}")
            failures += 1
            continue

        if healthy:
            print(f"PASS {name}: HTTP {status}")
        else:
            print(f"FAIL {name}: unexpected HTTP response")
            failures += 1

    if failures:
        print(f"Smoke test failed: {failures} check(s) did not pass.")
        return 1

    print("Smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
