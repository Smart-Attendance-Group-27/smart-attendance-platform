"""Atomically set the image tag in a protected VPS environment file."""

from __future__ import annotations

import argparse
import os
import stat
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", type=Path, default=Path("/etc/uniattend/private.env"))
    parser.add_argument("--sha", required=True)
    args = parser.parse_args()
    if len(args.sha) != 40 or any(char not in "0123456789abcdef" for char in args.sha):
        raise ValueError("Full lowercase Git SHA required")
    lines = args.env.read_text(encoding="utf-8").splitlines()
    matches = [index for index, line in enumerate(lines) if line.startswith("IMAGE_TAG=")]
    if len(matches) != 1:
        raise ValueError("Expected exactly one IMAGE_TAG entry")
    lines[matches[0]] = f"IMAGE_TAG='{args.sha}'"
    temporary = args.env.with_name(args.env.name + ".tmp")
    original = args.env.stat()
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        os.fchmod(output.fileno(), stat.S_IMODE(original.st_mode))
        os.fchown(output.fileno(), original.st_uid, original.st_gid)
        output.write("\n".join(lines) + "\n")
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary, args.env)
    print("Protected image tag updated.")


if __name__ == "__main__":
    main()
