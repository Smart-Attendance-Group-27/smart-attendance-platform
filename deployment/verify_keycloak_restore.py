"""Decrypt an off-host Keycloak backup and restore into isolated PostgreSQL.

The age identity stays on the workstation. Only the decrypted archive travels
over the existing encrypted SSH connection to a throwaway, networkless container.
"""

from __future__ import annotations

import argparse
import shlex
import subprocess
import time
from pathlib import Path


CONTAINER = "uniattend-keycloak-restore-check"


def run_ssh(*args: str, input_data: bytes | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "uniattend-vps", shlex.join(args)],
        input=input_data,
        capture_output=True,
        check=False,
        timeout=120,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--age", type=Path, required=True)
    parser.add_argument("--key", type=Path, required=True)
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--min-users", type=int, default=0)
    args = parser.parse_args()

    decrypted = subprocess.run(
        [str(args.age), "--decrypt", "-i", str(args.key), str(args.backup)],
        capture_output=True,
        check=False,
    )
    if decrypted.returncode != 0 or not decrypted.stdout.startswith(b"PGDMP"):
        raise RuntimeError("Keycloak backup decryption failed")

    created = run_ssh(
        "docker", "run", "-d", "--rm", "--name", CONTAINER,
        "--network", "none", "-e", "POSTGRES_HOST_AUTH_METHOD=trust",
        "postgres:16-alpine",
    )
    if created.returncode != 0:
        raise RuntimeError("Could not start isolated restore database")

    try:
        ready = False
        for _ in range(30):
            result = run_ssh("docker", "exec", CONTAINER, "pg_isready", "-U", "postgres")
            if result.returncode == 0:
                ready = True
                break
            time.sleep(1)
        if not ready:
            raise RuntimeError("Restore database did not start")

        restored = run_ssh(
            "docker", "exec", "-i", CONTAINER, "pg_restore", "-U", "postgres",
            "-d", "postgres", "--create", "--exit-on-error", "--no-owner",
            "--no-acl", input_data=decrypted.stdout,
        )
        if restored.returncode != 0:
            raise RuntimeError("Keycloak backup could not be restored")
        checked = run_ssh(
            "docker", "exec", CONTAINER, "psql", "-U", "postgres", "-d", "keycloak",
            "-A", "-t", "-c", "SELECT count(*) FROM public.realm",
        )
        if checked.returncode != 0:
            detail = checked.stderr.decode("utf-8", errors="replace").splitlines()
            raise RuntimeError(
                "Restored Keycloak realm query failed: "
                + (detail[0][:160] if detail else "unknown database error")
            )
        if int(checked.stdout.strip()) < 1:
            raise RuntimeError("Restored Keycloak realm is empty")
        users = run_ssh(
            "docker", "exec", CONTAINER, "psql", "-U", "postgres", "-d", "keycloak",
            "-A", "-t", "-c", "SELECT count(*) FROM public.user_entity",
        )
        if users.returncode != 0 or int(users.stdout.strip()) < args.min_users:
            raise RuntimeError("Restored Keycloak user count is too low")
        print("Keycloak backup decrypted off-host and restored to isolated PostgreSQL.")
    finally:
        run_ssh("docker", "rm", "-f", CONTAINER)


if __name__ == "__main__":
    main()
