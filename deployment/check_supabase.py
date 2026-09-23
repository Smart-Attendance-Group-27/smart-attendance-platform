"""Check the external PostgreSQL route without printing connection details."""

from __future__ import annotations

import argparse
import os
import statistics
import subprocess
import time
from pathlib import Path
from urllib.parse import unquote, urlparse

from render_realm import parse_env


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=5)
    args = parser.parse_args()

    parsed = urlparse(parse_env(args.env)["CORE_DB_URI"])
    if not parsed.hostname or not parsed.username or parsed.password is None:
        raise ValueError("CORE_DB_URI is incomplete")
    child_env = os.environ.copy()
    child_env.update(
        PGHOST=parsed.hostname,
        PGPORT=str(parsed.port or 5432),
        PGUSER=unquote(parsed.username),
        PGPASSWORD=unquote(parsed.password),
        PGDATABASE=parsed.path.lstrip("/"),
        PGSSLMODE="require",
        PGCONNECT_TIMEOUT="15",
    )
    samples: list[float] = []
    for _ in range(args.samples):
        started = time.perf_counter()
        completed = subprocess.run(
            ["psql", "-X", "-A", "-t", "-v", "ON_ERROR_STOP=1", "-c",
             "\\conninfo"],
            env=child_env,
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
        )
        if completed.returncode != 0 or "SSL connection" not in completed.stdout:
            error = completed.stderr.lower()
            if "password authentication failed" in error:
                reason = "authentication rejected"
            elif "could not translate host name" in error:
                reason = "DNS lookup failed"
            elif "timeout" in error or "timed out" in error:
                reason = "connection timed out"
            elif "no route to host" in error or "network is unreachable" in error:
                reason = "network route unavailable"
            elif "certificate" in error or "ssl" in error:
                reason = "TLS negotiation failed"
            elif completed.returncode == 0:
                reason = "server did not report TLS enabled"
            else:
                reason = "database command failed"
            raise RuntimeError(f"Supabase connection check failed: {reason}")
        samples.append((time.perf_counter() - started) * 1000)
    print(
        "Supabase TLS: verified; "
        f"connection + query median: {statistics.median(samples):.0f} ms; "
        f"range: {min(samples):.0f}-{max(samples):.0f} ms"
    )


if __name__ == "__main__":
    main()
