"""The seam: where the model lives, or doesn't.

One decision, made in one place:

  * mock  deterministic reasoners stand in for every model call. No key, no
          network, no spend. This is the DEFAULT, it is what CI runs, and it is
          what every milestone gate is measured on.
  * llm   the real OpenAI Agents SDK over LiteLLM -> AWS Bedrock. Selected only
          when credentials are present AND --mock was not passed.

The pipeline, the guardrails, the scorecard and the write-back are identical on
both paths. Swapping the brain changes how the judgment stages reason and
nothing else — which is the whole claim the architecture makes, so it is worth
it being literally true rather than approximately true.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

# Defaults, overridable per deployment. Cross-region Bedrock inference
# profiles; `bedrock/converse/` is the prefix LiteLLM routes to the Converse
# API. Verify the two profiles are enabled in the account with
# `aws bedrock list-inference-profiles` — an unavailable profile fails at the
# first model call, not at startup.
DEFAULT_FAST = "bedrock/converse/us.anthropic.claude-haiku-4-5-20251001-v1:0"
DEFAULT_SMART = "bedrock/converse/us.anthropic.claude-sonnet-4-5-20250929-v1:0"

# Which stage gets which TIER. Coverage is the money step and the only stage
# that concludes on cover, so it is the only one that earns the smart model.
#
# Roles, not model ids, and that is the fix for a real bug: these used to be
# resolved strings captured at import time, which meant the table went stale
# the moment CLAIMSENSE_MODEL_* was set and silently disagreed with what
# actually ran. A role cannot go stale.
STAGE_MODEL: dict[str, str] = {
    "triage": "fast",
    "evidence": "fast",
    "coverage": "smart",     # the money step
    "risk": "fast",
    "adjudicator": "fast",
}


def model_fast() -> str:
    """Read at CALL time, never at import time.

    cli.py imports this module before it calls systems.load_env(), so a
    module-level `os.environ.get(...)` captured the default and the
    CLAIMSENSE_MODEL_FAST line that .env.example documents did nothing at all.
    A cost control that is documented but not wired is worse than no control,
    because it is defended by a screenshot of the config file.
    """
    return os.environ.get("CLAIMSENSE_MODEL_FAST", DEFAULT_FAST)


def model_smart() -> str:
    return os.environ.get("CLAIMSENSE_MODEL_SMART", DEFAULT_SMART)


@dataclass
class BrainConfig:
    mode: str           # mock | llm
    provider: str       # none | bedrock | openai
    fast: str | None = None
    smart: str | None = None

    @property
    def is_mock(self) -> bool:
        return self.mode == "mock"

    def for_stage(self, stage: str) -> str | None:
        """The model a given stage runs on — the routing table, resolved."""
        return self.smart if STAGE_MODEL.get(stage) == "smart" else self.fast

    def describe(self) -> str:
        if self.is_mock:
            return "mock (deterministic reasoners — no key, no network, $0)"
        return (f"{self.provider}: fast={self.fast.split('/')[-1]} "
                f"smart={self.smart.split('/')[-1]}")


def detect(force_mock: bool) -> BrainConfig:
    """Decide which brain runs. --mock always wins.

    With no credentials anywhere this falls back to mock rather than failing.
    A demo that dies because a key is missing is a demo that cannot be given,
    and the mock path is a genuine rehearsal rather than a stub.
    """
    if force_mock:
        return BrainConfig(mode="mock", provider="none")

    if os.environ.get("AWS_ACCESS_KEY_ID") or os.environ.get("AWS_PROFILE"):
        return BrainConfig(mode="llm", provider="bedrock",
                           fast=model_fast(), smart=model_smart())
    if os.environ.get("OPENAI_API_KEY"):
        model = os.environ.get("CLAIMSENSE_MODEL", "gpt-5.4-mini")
        return BrainConfig(mode="llm", provider="openai", fast=model, smart=model)

    return BrainConfig(mode="mock", provider="none")
