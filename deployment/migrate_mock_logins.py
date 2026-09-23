"""Recreate the previously linked pilot logins on the new Keycloak.

Run once on the VPS with an encrypted Supabase backup already taken. The
credentials file must be copied to protected off-host storage after success.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import secrets
import subprocess
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import unquote, urlencode, urlparse
from urllib.request import Request, urlopen

from render_realm import parse_env


ACCOUNTS = {
    "admin@uniattend.test": ("a835eb36-3227-4dae-a453-6022b273c56b", "ADMINISTRATOR"),
    "admin01@lectuere.uniattend.test": ("e66d4bf5-ed74-4f55-8ca8-6754199605db", "ADMINISTRATOR"),
    "lecutere01@lectuere.uniattend.test": ("325e2cdd-71b6-417e-bb6e-3c990ac7aace", "LECTURER"),
    "lecutere02@lectuere.uniattend.test": ("22bd9602-6061-4869-9766-83f7ec03b24a", "LECTURER"),
    "230701a@student.uniattend.test": ("eb39470c-a1e7-4249-867c-e518401c8b49", "STUDENT"),
    "230736r@student.uniattend.test": ("659a6da3-e6ab-4740-9ea3-2212948b9f27", "STUDENT"),
    "230737r@student.uniattend.test": ("8fb03922-5c9c-4734-a823-e3f4932925eb", "STUDENT"),
}
DISPLAY_NAMES = {
    "admin@uniattend.test": ("System", "Administrator"),
    "admin01@lectuere.uniattend.test": ("Kamal", "Perera"),
    "lecutere01@lectuere.uniattend.test": ("Indika", "Perera"),
    "lecutere02@lectuere.uniattend.test": ("Dulani", "Meedeniya"),
    "230701a@student.uniattend.test": ("Amal", "Perera"),
    "230736r@student.uniattend.test": ("Manushan", "Student"),
    "230737r@student.uniattend.test": ("Anura", "Kumara"),
}
INACTIVE_ACCOUNTS = {
    "lecturer.local@uniattend.test": "921ed166-2ca2-487e-9c82-ec948a96a2ca",
    "student.local@uniattend.test": "c6842801-78f2-4d94-aa4e-f3d94437ca52",
}
KEYCLOAK = "http://127.0.0.1:8080"


def api(path: str, token: str, method: str = "GET", payload: object | None = None):
    body = None if payload is None else json.dumps(payload).encode()
    headers = {"Authorization": f"Bearer {token}"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    with urlopen(Request(KEYCLOAK + path, data=body, headers=headers, method=method), timeout=20) as response:
        content = response.read()
        return response.status, response.headers, json.loads(content) if content else None


def database_env(values: dict[str, str]) -> dict[str, str]:
    uri = urlparse(values["CORE_DB_URI"])
    if not uri.hostname or not uri.hostname.endswith(".supabase.com"):
        raise RuntimeError("Expected Supabase database")
    result = os.environ.copy()
    result.update(
        PGHOST=uri.hostname,
        PGPORT=str(uri.port or 5432),
        PGUSER=unquote(uri.username or ""),
        PGPASSWORD=unquote(uri.password or ""),
        PGDATABASE=uri.path.lstrip("/"),
        PGSSLMODE="require",
        PGCONNECT_TIMEOUT="15",
    )
    return result


def psql(sql: str, env: dict[str, str]) -> str:
    result = subprocess.run(
        ["psql", "-X", "-v", "ON_ERROR_STOP=1", "-A", "-F", "|", "-t"],
        input=sql, text=True, capture_output=True, env=env, check=False,
    )
    if result.returncode:
        raise RuntimeError("Supabase SQL failed: " + result.stderr.strip()[:500])
    return result.stdout


def verify_database(env: dict[str, str]) -> None:
    rows = csv.reader(io.StringIO(psql("""
        SELECT u.email, u.keycloak_user_id, r.role_code
        FROM identity.users u
        LEFT JOIN identity.user_roles ur ON ur.user_id = u.id
        LEFT JOIN identity.roles r ON r.id = ur.role_id
        WHERE u.keycloak_user_id IS NOT NULL
        ORDER BY u.email, r.role_code;
    """, env)), delimiter="|")
    actual = {row[0]: (row[1], row[2]) for row in rows if row}
    expected = {**ACCOUNTS, **{key: (value, "") for key, value in INACTIVE_ACCOUNTS.items()}}
    if actual != expected:
        raise RuntimeError("Linked Supabase users differ from the audited account set")


def quoted(value: str) -> str:
    if not re.fullmatch(r"[a-z0-9@.\-]+|[0-9a-f-]{36}", value):
        raise ValueError("Unsafe account value")
    return "'" + value + "'"


def update_database(created: list[tuple[str, str, str]], env: dict[str, str]) -> None:
    statements = ["BEGIN;", "DO $$", "DECLARE changed integer;", "BEGIN"]
    for email, identifier, _password in created:
        old_identifier = ACCOUNTS[email][0]
        statements.extend([
            "UPDATE identity.users SET keycloak_user_id = " + quoted(identifier)
            + ", updated_at = now() WHERE email = " + quoted(email)
            + " AND keycloak_user_id = " + quoted(old_identifier) + ";",
            "GET DIAGNOSTICS changed = ROW_COUNT;",
            "IF changed <> 1 THEN RAISE EXCEPTION 'Pilot user remap count mismatch'; END IF;",
        ])
    for email, old_identifier in INACTIVE_ACCOUNTS.items():
        statements.extend([
            "UPDATE identity.users SET keycloak_user_id = NULL, account_status = 'inactive', updated_at = now()"
            + " WHERE email = " + quoted(email) + " AND keycloak_user_id = " + quoted(old_identifier) + ";",
            "GET DIAGNOSTICS changed = ROW_COUNT;",
            "IF changed <> 1 THEN RAISE EXCEPTION 'Unused user deactivation count mismatch'; END IF;",
        ])
    statements.extend(["END $$;", "COMMIT;"])
    psql("\n".join(statements), env)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", type=Path, default=Path("/etc/uniattend/private.env"))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise FileExistsError(args.out)
    values = parse_env(args.env)
    db_env = database_env(values)
    verify_database(db_env)
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

    roles = {}
    for role in ("administrator", "lecturer", "student"):
        _, _, roles[role] = api(f"/admin/realms/uniattend/roles/{role}", token)

    created: list[tuple[str, str, str]] = []
    database_updated = False
    try:
        for email, (_old, role_code) in ACCOUNTS.items():
            password = secrets.token_urlsafe(24)
            first_name, last_name = DISPLAY_NAMES[email]
            status, headers, _ = api("/admin/realms/uniattend/users", token, "POST", {
                "username": email, "email": email, "enabled": True,
                "emailVerified": True,
                "firstName": first_name, "lastName": last_name,
                "credentials": [{"type": "password", "value": password, "temporary": False}],
            })
            if status != 201:
                raise RuntimeError("Keycloak user creation failed")
            identifier = headers["Location"].rstrip("/").rsplit("/", 1)[-1]
            if not re.fullmatch(r"[0-9a-f-]{36}", identifier):
                raise RuntimeError("Keycloak did not return a user UUID")
            created.append((email, identifier, password))
            api(f"/admin/realms/uniattend/users/{identifier}/role-mappings/realm",
                token, "POST", [roles[role_code.lower()]])

        # Persist recovery credentials before committing the cross-service remap.
        args.out.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(args.out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            output.write("Pilot Keycloak logins (change passwords after handoff)\n")
            output.write("URL: " + values["KEYCLOAK_PUBLIC_URL"] + "\n\n")
            for email, _identifier, password in created:
                output.write(f"{ACCOUNTS[email][1]} | {email} | {password}\n")
            output.flush()
            os.fsync(output.fileno())
        update_database(created, db_env)
        database_updated = True
    finally:
        if not database_updated:
            if args.out.exists():
                args.out.unlink()
            for _email, identifier, _password in created:
                try:
                    api(f"/admin/realms/uniattend/users/{identifier}", token, "DELETE")
                except HTTPError:
                    pass
    print("Seven role-bearing mock logins remapped; two record-bearing unused logins deactivated.")


if __name__ == "__main__":
    main()
