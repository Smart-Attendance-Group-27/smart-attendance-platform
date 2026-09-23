"""Render the local realm template with release-specific clients and URLs.

The output contains secrets. Keep it outside Git and restrict it to 0600.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            key, separator, value = line.partition("=")
            if not separator:
                raise ValueError("Invalid environment file")
            values[key] = value.strip().strip('"').strip("'")
    return values


def render(template: dict, values: dict[str, str]) -> dict:
    web_url = values["WEB_BASE_URL"].rstrip("/")
    web_secret = values["WEB_KEYCLOAK_CLIENT_SECRET"]
    provisioner_secret = values["KEYCLOAK_ADMIN_CLIENT_SECRET"]
    if any(len(secret) < 32 for secret in (web_secret, provisioner_secret)):
        raise ValueError("Keycloak client secrets must have at least 32 characters")

    clients = {client["clientId"]: client for client in template["clients"]}
    web = clients["uniattend-web"]
    web["secret"] = web_secret
    web["redirectUris"] = [f"{web_url}/api/auth/callback"]
    web["webOrigins"] = [web_url]
    web["attributes"]["post.logout.redirect.uris"] = f"{web_url}/login"
    clients["uniattend-provisioner"]["secret"] = provisioner_secret
    return template


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    template_path = (
        Path(__file__).resolve().parents[1]
        / "infra/local/keycloak/realm/uniattend-realm.json"
    )
    template = json.loads(template_path.read_text(encoding="utf-8"))
    rendered = render(template, parse_env(args.env))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(args.out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as output:
        json.dump(rendered, output, indent=2)
        output.write("\n")
    print("Realm rendered with restricted permissions.")


if __name__ == "__main__":
    main()
