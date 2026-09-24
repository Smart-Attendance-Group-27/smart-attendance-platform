"""Check the tunnel-only VPS stack without exposing secrets or tokens."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from render_realm import parse_env


def get_json(url: str) -> dict:
    with urlopen(url, timeout=15) as response:
        if response.status != 200:
            raise RuntimeError("Unexpected health response")
        return json.load(response)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", type=Path, default=Path("/etc/uniattend/private.env"))
    args = parser.parse_args()
    values = parse_env(args.env)

    for name, url in (
        ("Core process", "http://127.0.0.1:8000/health"),
        ("Core database", "http://127.0.0.1:8000/health/db"),
        ("Face process/model", "http://127.0.0.1:8001/health"),
        ("Face database", "http://127.0.0.1:8001/health/db"),
    ):
        if get_json(url).get("status") != "ok":
            raise RuntimeError(f"{name} failed")
        print(f"PASS {name}")

    with urlopen("http://127.0.0.1:3000/", timeout=15) as response:
        if response.status != 200:
            raise RuntimeError("Web failed")
    print("PASS Web")

    discovery = get_json(
        "http://127.0.0.1:8080/realms/uniattend/.well-known/openid-configuration"
    )
    if discovery.get("issuer") != values["KEYCLOAK_EXPECTED_ISSUER"]:
        raise RuntimeError("Keycloak issuer mismatch")
    print("PASS Keycloak discovery and public issuer")

    body = urlencode(
        {
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": values["KEYCLOAK_ADMIN_USERNAME"],
            "password": values["KEYCLOAK_ADMIN_PASSWORD"],
        }
    ).encode("ascii")
    request = Request(
        "http://127.0.0.1:8080/realms/master/protocol/openid-connect/token",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urlopen(request, timeout=15) as response:
        token = json.load(response).get("access_token")
    if not token:
        raise RuntimeError("Keycloak administrator token not issued")
    print("PASS Keycloak administrator token issuance")

    request = Request(
        "http://127.0.0.1:8080/admin/realms/uniattend",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urlopen(request, timeout=15) as response:
        realm = json.load(response)
    if realm.get("realm") != "uniattend":
        raise RuntimeError("Keycloak realm import failed")
    print("PASS Keycloak realm import and Admin API")

    core_to_face = subprocess.run(
        ["docker", "exec", "uniattend-app-core-api-1", "python", "-c",
         "import urllib.request; print(urllib.request.urlopen('http://face-verification:8001/health', timeout=10).status)"],
        capture_output=True,
        text=True,
        check=False,
    )
    if core_to_face.returncode != 0 or core_to_face.stdout.strip() != "200":
        raise RuntimeError("Core-to-Face internal route failed")
    print("PASS Core-to-Face internal route")


if __name__ == "__main__":
    main()
