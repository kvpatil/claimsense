"""The gate must EXIT non-zero when it fails.

This file exists because of a real bug. `__main__.py` called `main()` without
`sys.exit(...)`, so the eval gate printed GATE FAILED in red and the process
still exited 0. Every visible signal said the gate worked; the only thing that
disagreed was `$?`, which is the only thing CI reads.

The milestone requirement is that a failing evaluation blocks the image push.
That requirement lives entirely in an exit code, so it gets its own test, and
the test runs the CLI as a SUBPROCESS rather than calling run_suite directly —
calling the function would check the return value and miss exactly the bug
that happened.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

AGENT = Path(__file__).resolve().parent.parent
FIXTURE = AGENT / "data" / "fixture.json"


def run_gate(suite: str, min_pass: str,
             claims: str = "") -> subprocess.CompletedProcess:
    args = [sys.executable, "-m", "claimsense_agent", "eval",
            "--suite", suite, "--min-pass", min_pass, "--mock"]
    if claims:
        args += ["--claims", claims]
    return subprocess.run(
        args,
        cwd=AGENT, capture_output=True, text=True,
        env={"PYTHONPATH": "src", "PATH": "/usr/bin:/bin", "NO_COLOR": "1"},
    )


@pytest.fixture
def broken_fixture(tmp_path):
    """Regress some eval expectations, then always put the fixture back."""
    backup = tmp_path / "fixture.json"
    shutil.copy(FIXTURE, backup)

    def break_claims(claim_ids, to="APPROVE"):
        data = json.loads(FIXTURE.read_text())
        for cid in claim_ids:
            data["claims"][str(cid)]["_expect"] = to
        FIXTURE.write_text(json.dumps(data))

    yield break_claims
    shutil.copy(backup, FIXTURE)


def test_passing_gate_exits_zero():
    result = run_gate("smoke", "0.9")
    assert "GATE PASSED" in result.stdout
    assert result.returncode == 0


def test_failing_rate_exits_nonzero(broken_fixture):
    """Three regressions take 20 cases to 85%, under the 90% bar."""
    broken_fixture([4402, 4403, 4413])
    result = run_gate("smoke", "0.9")
    assert "GATE FAILED" in result.stdout
    assert result.returncode != 0, (
        "the gate printed GATE FAILED but exited 0 — CI would go green on a "
        "red gate, and the image would be pushed")


def test_adversarial_regression_exits_nonzero(broken_fixture):
    """One adversarial failure sinks the golden gate even at 95%.

    Averaging a safety failure away against nineteen easy passes is how a
    guardrail regression ships.
    """
    broken_fixture([4420])              # ADV-05, the poisoned FNOL
    result = run_gate("golden", "0.95")
    assert "95%" in result.stdout       # the RATE is fine…
    assert "adversarial case(s) regressed" in result.stdout   # …and it still fails
    assert result.returncode != 0


def test_missing_outcome_fails_the_gate():
    """A suite that never PRODUCES SIU_REFERRAL is not testing fraud routing.

    The check reads the outcomes the pipeline actually reached, not what the
    cases expected — so it is exercised by narrowing the suite rather than by
    editing expectations. Claims 4401-4404 yield APPROVE, DENY, DENY and
    MORE_INFO: every case passes, the rate is 100%, and the gate must still
    fail because fraud routing was never exercised.
    """
    result = run_gate("smoke", "0.0", claims="4401-4404")
    assert "100%" in result.stdout, "every selected case should pass on merit"
    assert "never produced" in result.stdout
    assert "SIU_REFERRAL" in result.stdout
    assert result.returncode != 0, (
        "a suite that exercises three of the four outcomes reported a green "
        "gate — coverage of the outcome space is part of the gate, not a "
        "property of the average")
