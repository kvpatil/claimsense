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
# Adjuster 5 is the ClaimSense service seat: scope 'all' so it can read any
# claim in the queue, licence NULL so it can never confirm its own
# recommendation. The agent is refused by exactly the same check that refuses
# the SIU analyst — there is no special case for it anywhere in the code.
AGENT_SEAT = 5
SYSTEMS = [("cms", AGENT_SEAT, "claimsense agent — claims management"),
           ("pas", AGENT_SEAT, "claimsense agent — policy administration"),
           ("dms", AGENT_SEAT, "claimsense agent — document store")]


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


KEYS_ENV = HERE.parent.parent / "keys.env"
EXAMPLE = HERE.parent.parent / "keys.env.example"


def write_keys_env(minted: list[tuple[str, str]]) -> bool:
    """Put the minted keys straight into keys.env.

    Printing them and asking for copy-paste is how a key ends up in a shell
    history, a scrollback buffer or a screenshot. Writing the file is one less
    place the plaintext exists.

    Only the three CMS_/PAS_/DMS_ lines are touched; anything else already in
    the file — an AWS key, an OpenAI key — is preserved exactly.
    """
    if not KEYS_ENV.exists():
        if not EXAMPLE.exists():
            return False
        KEYS_ENV.write_text(EXAMPLE.read_text())

    lines = KEYS_ENV.read_text().splitlines()
    wanted = {f"{system.upper()}_API_KEY": key for system, key in minted}
    seen = set()
    out = []
    for line in lines:
        name = line.split("=", 1)[0].strip() if "=" in line else ""
        if name in wanted:
            out.append(f"{name}={wanted[name]}")
            seen.add(name)
        else:
            out.append(line)
    for name, value in wanted.items():
        if name not in seen:
            out.append(f"{name}={value}")

    KEYS_ENV.write_text("\n".join(out) + "\n")
    # 0600: the file holds live credentials and there is no reason for anything
    # but this user to read it.
    KEYS_ENV.chmod(0o600)
    return True


def main() -> None:
    minted = []
    for system, adjuster_id, label in SYSTEMS:
        # csk_ prefix so a leaked key is greppable in a diff or a log.
        key = f"csk_{system}_{secrets.token_urlsafe(24)}"
        digest = hashlib.sha256(key.encode()).hexdigest()
        psql("INSERT INTO platform.api_keys (key_hash, system, adjuster_id, label) "
             f"VALUES ('{digest}', '{system}', {adjuster_id}, '{label}');")
        minted.append((system, key))

    wrote = write_keys_env(minted)
    print()
    if wrote:
        print(f"  Scoped API keys written to {KEYS_ENV.name} (mode 0600).")
        print("  Stored in the database as sha256 only — this file is the one")
        print("  copy of the plaintext, and it is gitignored.")
        print()
        for system, _ in minted:
            print(f"    {system.upper()}_API_KEY  ✓ written")
    else:
        width = max(len(k) for _, k in minted)
        print("  Scoped API keys — printed ONCE, stored only as sha256.")
        print("  Copy these into keys.env; they cannot be recovered afterwards.")
        print()
        for system, key in minted:
            print(f"    {system.upper()}_API_KEY={key:<{width}}")
    print()


if __name__ == "__main__":
    main()
