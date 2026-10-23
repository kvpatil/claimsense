"""Mint scoped API keys — one per client system.

Three keys, not one. CMS, PAS and DMS are three separate vendor systems with
three separate contracts, so a credential for one must not open the other two;
`platform.api_keys.system` is what enforces that at the API layer.

The plaintext is printed ONCE and never stored — only the sha256 hash reaches
the database. Re-running mints a fresh set and revokes nothing, which is
deliberate: rotation should be additive, and revocation should be explicit.
"""
from __future__ import annotations

import hashlib
import os
import secrets
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SYSTEMS = [("cms", 1, "agent — claims management"),
           ("pas", 1, "agent — policy administration"),
           ("dms", 1, "agent — document store")]


def psql(sql: str) -> str:
    out = subprocess.run(
        ["docker", "compose", "-f", str(HERE / "docker-compose.yml"), "exec", "-T",
         "claimsense-db", "psql", "-U", "claimsense", "-d", "claimsense",
         "-q", "-t", "-A", "-v", "ON_ERROR_STOP=1", "-c", sql],
        capture_output=True, text=True)
    if out.returncode != 0:
        sys.stderr.write(out.stderr)
        raise SystemExit(f"psql failed: {out.returncode}")
    return out.stdout.strip()


def main() -> None:
    minted = []
    for system, adjuster_id, label in SYSTEMS:
        # csk_ prefix so a leaked key is greppable in a diff or a log.
        key = f"csk_{system}_{secrets.token_urlsafe(24)}"
        digest = hashlib.sha256(key.encode()).hexdigest()
        psql("INSERT INTO platform.api_keys (key_hash, system, adjuster_id, label) "
             f"VALUES ('{digest}', '{system}', {adjuster_id}, '{label}');")
        minted.append((system, key))

    width = max(len(k) for _, k in minted)
    print()
    print("  Scoped API keys — printed ONCE, stored only as sha256.")
    print("  Copy these into .env; they cannot be recovered afterwards.")
    print()
    for system, key in minted:
        print(f"  {system.upper()}_API_KEY={key:<{width}}")
    print()


if __name__ == "__main__":
    main()
