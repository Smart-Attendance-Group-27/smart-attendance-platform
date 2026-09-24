"""Idempotently complete display names for the audited pilot Keycloak users."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from migrate_mock_logins import ACCOUNTS, DISPLAY_NAMES, KEYCLOAK, api, database_env, psql
from render_realm import parse_env


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", type=Path, default=Path("/etc/uniattend/private.env"))
    args = parser.parse_args()
    values = parse_env(args.env)
    rows = psql("""
        SELECT email, keycloak_user_id FROM identity.users
        WHERE email IN (
          'admin@uniattend.test', 'admin01@lectuere.uniattend.test',
          'lecutere01@lectuere.uniattend.test', 'lecutere02@lectuere.uniattend.test',
          '230701a@student.uniattend.test', '230736r@student.uniattend.test',
          '230737r@student.uniattend.test'
        ) ORDER BY email;
    """, database_env(values))
    ids = dict(line.split("|", 1) for line in rows.splitlines())
    if set(ids) != set(ACCOUNTS) or any(not identifier for identifier in ids.values()):
        raise RuntimeError("Pilot Supabase links are incomplete")
    body = urlencode({
        "grant_type": "password", "client_id": "admin-cli",
        "username": values["KEYCLOAK_ADMIN_USERNAME"],
        "password": values["KEYCLOAK_ADMIN_PASSWORD"],
    }).encode()
    with urlopen(Request(
        KEYCLOAK + "/realms/master/protocol/openid-connect/token", data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    ), timeout=20) as response:
        token = json.load(response)["access_token"]
    for email, identifier in ids.items():
        first_name, last_name = DISPLAY_NAMES[email]
        status, _headers, _body = api(
            f"/admin/realms/uniattend/users/{identifier}", token, "PUT",
            {"firstName": first_name, "lastName": last_name},
        )
        if status != 204:
            raise RuntimeError("Keycloak profile update failed")
    print("Seven pilot Keycloak display profiles synchronized.")


if __name__ == "__main__":
    main()
