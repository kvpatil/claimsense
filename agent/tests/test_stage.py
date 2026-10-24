"""The engagement stage, and what it gates.

Week 4 capabilities are built and tested; this decides whether they are
reachable. These tests exist because "we built it early" is not a reason to
claim it in the wrong week, and a gate nobody checks is a gate that drifts
open.
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys

import pytest

from claimsense_agent import stage

AGENT = pathlib.Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.delenv(stage.ENV_VAR, raising=False)


def test_default_is_week3():
    """Week 3 is the default, so an unconfigured stack cannot overclaim."""
    assert stage.current() == stage.WEEK3
    assert stage.integration_enabled() is False


def test_week4_enables_integration(monkeypatch):
    monkeypatch.setenv(stage.ENV_VAR, stage.WEEK4)
    assert stage.integration_enabled() is True


@pytest.mark.parametrize("raw", ["WEEK4", " week4 ", "Week4"])
def test_casing_and_whitespace_are_tolerated(monkeypatch, raw):
    """A value from a .env file or a shell export should not need to be exact."""
    monkeypatch.setenv(stage.ENV_VAR, raw)
    assert stage.current() == stage.WEEK4


@pytest.mark.parametrize("raw", ["wek4", "week5", "4", "true", "yes"])
def test_an_unknown_stage_raises(monkeypatch, raw):
    """Loud, not a silent fallback to week3.

    A typo would otherwise disable the write-back at exactly the moment
    someone is demonstrating it, and the symptom — a refusal naming week3 —
    points away from the cause.
    """
    monkeypatch.setenv(stage.ENV_VAR, raw)
    with pytest.raises(stage.UnknownStage) as exc:
        stage.current()
    assert stage.ENV_VAR in str(exc.value)
    assert raw in str(exc.value)


def test_an_empty_value_is_the_default(monkeypatch):
    """CLAIMSENSE_STAGE= in a .env file means 'unset', not 'invalid'."""
    monkeypatch.setenv(stage.ENV_VAR, "")
    assert stage.current() == stage.WEEK3


def test_the_refusal_says_how_to_lift_itself():
    msg = stage.refusal("--write")
    assert stage.ENV_VAR in msg and stage.WEEK4 in msg
    assert "Week 4" in msg


# ---- the CLI, as a subprocess ------------------------------------------
# Run out of process on purpose: the thing under test is the exit code and
# what reaches stdout, and calling main() directly would check neither.

def run_cli(args, stage_value=None):
    env = {"PYTHONPATH": "src", "PATH": "/usr/bin:/bin", "NO_COLOR": "1"}
    if stage_value is not None:
        env[stage.ENV_VAR] = stage_value
    return subprocess.run([sys.executable, "-m", "claimsense_agent", *args],
                          cwd=AGENT, capture_output=True, text=True, env=env)


def test_write_is_refused_at_week3():
    r = run_cli(["run", "--claim", "4414", "--mock", "--write"])
    assert "Week 4 scope" in r.stdout
    assert stage.ENV_VAR in r.stdout
    # Non-zero, so a script cannot mistake a refusal for a successful write.
    assert r.returncode != 0


def test_the_run_still_completes_when_the_write_is_refused():
    """The pipeline worked. Only the step into Northwind's workflow is withheld.

    Refusing the whole run would make the stage flag feel like breakage, and
    the scorecard is exactly what Week 3 is meant to produce.
    """
    r = run_cli(["run", "--claim", "4414", "--mock", "--write"])
    assert "SCORECARD" in r.stdout
    assert "APPROVE" in r.stdout


def test_a_plain_run_is_unaffected_by_the_stage():
    for value in (None, stage.WEEK3, stage.WEEK4):
        r = run_cli(["run", "--claim", "4414", "--mock"], stage_value=value)
        assert r.returncode == 0, f"stage={value}: {r.stdout[-400:]}"


def test_an_unknown_stage_stops_the_cli_before_any_work():
    r = run_cli(["run", "--claim", "4414", "--mock"], stage_value="wek4")
    assert r.returncode == 2
    assert "is not a stage" in r.stderr
    assert "SCORECARD" not in r.stdout, "it should fail before running anything"


# ---- the two definitions must not drift --------------------------------

def test_the_portal_mirrors_the_python_definition():
    """stage.py and lib/stage.js are two readers of one rule.

    Checked mechanically rather than by remembering: a stage added to one and
    not the other would mean the agent and the portal disagree about which
    week the stack is running as.
    """
    js = (AGENT.parent / "platform" / "web" / "src" / "lib" / "stage.js")
    if not js.exists():          # agent container ships without platform/
        pytest.skip("portal source not present")
    src = js.read_text()

    assert f'"{stage.ENV_VAR}"' in src
    for name in stage.STAGES:
        assert f'"{name}"' in src, f"{name} missing from the portal reader"
    # The default must match, or an unconfigured portal and agent disagree.
    assert re.search(r"\?\?\s*WEEK3", src), "portal must default to week3"
