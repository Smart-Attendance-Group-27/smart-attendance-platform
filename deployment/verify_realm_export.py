"""Verify an encrypted off-host Keycloak realm export without printing secrets."""

from __future__ import annotations

import argparse
import io
import json
import subprocess
import tarfile
from pathlib import Path


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
    if decrypted.returncode != 0:
        raise RuntimeError("Realm export decryption failed")
    with tarfile.open(fileobj=io.BytesIO(decrypted.stdout), mode="r:") as archive:
        members = [entry for entry in archive.getmembers() if entry.isfile()]
        if len(members) != 1:
            raise RuntimeError("Realm export archive has an unexpected shape")
        source = archive.extractfile(members[0])
        if source is None:
            raise RuntimeError("Realm export JSON is missing")
        realm = json.load(source)
    clients = {client.get("clientId") for client in realm.get("clients", [])}
    if realm.get("realm") != "uniattend" or not {
        "uniattend-web", "uniattend-mobile", "uniattend-api", "uniattend-provisioner"
    }.issubset(clients):
        raise RuntimeError("Realm export is missing required clients")
    if len(realm.get("users", [])) < args.min_users:
        raise RuntimeError("Realm export contains fewer users than expected")
    print("Encrypted realm export decrypted off-host and required clients verified.")


if __name__ == "__main__":
    main()
