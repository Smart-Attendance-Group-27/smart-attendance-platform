"""Create and verify a full encrypted Supabase recovery archive.

Requires local pg_dump/pg_restore and the Python cryptography package. Neither
database credentials nor backup key are passed on a command line or printed.
"""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlparse

from cryptography.fernet import Fernet

from render_realm import parse_env


def write_exclusive(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as output:
        output.write(content)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-env", type=Path, required=True)
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--key", type=Path, required=True)
    parser.add_argument("--pg-bin", type=Path, required=True)
    args = parser.parse_args()

    if args.backup.exists() or args.key.exists():
        raise ValueError("Backup and key paths must be new files")
    uri = urlparse(parse_env(args.source_env)["CORE_DB_URI"])
    if not uri.hostname or not uri.username or uri.password is None:
        raise ValueError("Database URI is incomplete")
    env = os.environ.copy()
    env.update(
        PGHOST=uri.hostname,
        PGPORT=str(uri.port or 5432),
        PGUSER=unquote(uri.username),
        PGPASSWORD=unquote(uri.password),
        PGDATABASE=uri.path.lstrip("/"),
        PGSSLMODE="require",
        PGCONNECT_TIMEOUT="15",
    )
    dump = subprocess.run(
        [str(args.pg_bin / "pg_dump.exe"), "-Fc", "--no-owner", "--no-acl"],
        env=env,
        capture_output=True,
        check=False,
    )
    if dump.returncode != 0 or not dump.stdout.startswith(b"PGDMP"):
        raise RuntimeError("pg_dump did not produce a valid custom archive")
    key = Fernet.generate_key()
    encrypted = Fernet(key).encrypt(dump.stdout)
    restored = Fernet(key).decrypt(encrypted)
    listed = subprocess.run(
        [str(args.pg_bin / "pg_restore.exe"), "--list"],
        input=restored,
        capture_output=True,
        check=False,
    )
    if listed.returncode != 0 or b"TOC Entries" not in listed.stdout:
        raise RuntimeError("Encrypted archive failed pg_restore listing check")
    write_exclusive(args.backup, encrypted)
    write_exclusive(args.key, key + b"\n")
    print(f"Encrypted Supabase backup verified ({len(dump.stdout)} bytes before encryption).")


if __name__ == "__main__":
    main()
