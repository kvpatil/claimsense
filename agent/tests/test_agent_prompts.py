"""The prompts must describe the runtime the agents actually have.

A prompt that tells the model to hand off when it has no handoff tool is not a
cosmetic error: the model tries to comply, finds no tool, and is liable to
write prose where structured output was required — which then fails validation
and burns a retry. These are cheap guards against that drifting back in.
"""
from __future__ import annotations

import importlib
import pkgutil

import pytest

from claimsense_agent import agents as agents_pkg

# The three stages that reason. Risk and the adjudicator are code — see their
# module docstrings for why, and for the prompts they would have had.
AGENT_STAGES = ("triage", "evidence", "coverage")
CODE_STAGES = ("risk", "adjudicator")


def _mod(name):
    return importlib.import_module(f"claimsense_agent.agents.{name}")


@pytest.mark.parametrize("stage", AGENT_STAGES)
def test_each_agent_stage_has_a_prompt(stage):
    assert _mod(stage).INSTRUCTIONS.strip()


@pytest.mark.parametrize("stage", CODE_STAGES)
def test_code_stages_carry_no_unused_prompt(stage):
    """An unused INSTRUCTIONS beside deterministic code reads as an agent that
    was quietly switched off."""
    assert not hasattr(_mod(stage), "INSTRUCTIONS"), (
        f"{stage} runs as code; its prompt belongs in the module docstring")


@pytest.mark.parametrize("stage", AGENT_STAGES)
def test_no_prompt_promises_a_handoff(stage):
    """build_agents passes no handoffs= — the stages are driven one at a time
    so the guardrails can sit between them. See sdk_runtime's docstring."""
    text = _mod(stage).INSTRUCTIONS.lower()
    for phrase in ("hand off", "handoff", "hand it off"):
        assert phrase not in text, (
            f"{stage}'s prompt promises a {phrase!r} it has no tool for")


@pytest.mark.parametrize("stage", AGENT_STAGES)
def test_every_prompt_fences_untrusted_claimant_text(stage):
    """Prompt injection arrives inside the claimant's own narrative, which
    cannot be dropped because it is the evidence. Every agent that can see it
    must be told to report it and never obey it."""
    text = _mod(stage).INSTRUCTIONS
    assert "UNTRUSTED CLAIMANT TEXT" in text
    assert "never follow" in text.lower() or "never obey" in text.lower()


def test_no_stage_module_was_added_without_a_decision():
    """A new agents/*.py is either a judgment stage with a prompt or code
    without one. This fails on a third option, which is the thing that goes
    unnoticed."""
    found = {m.name for m in pkgutil.iter_modules(agents_pkg.__path__)
             if not m.name.startswith("_") and m.name != "sdk_runtime"}
    assert found == set(AGENT_STAGES) | set(CODE_STAGES), (
        f"unclassified stage module(s): {found ^ (set(AGENT_STAGES) | set(CODE_STAGES))}")
