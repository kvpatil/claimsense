"""The seam: where the model lives, or doesn't.

One decision, made in one place:

  * mock  deterministic reasoners stand in for every model call. No key, no
          network, no spend. This is the DEFAULT, it is what CI runs, and it is
          what every milestone gate is measured on.
  * llm   the real OpenAI Agents SDK over LiteLLM -> AWS Bedrock. Selected only
          when credentials are present AND --mock was not passed.

The pipeline, the guardrails, the scorecard and the write-back are identical on
both paths. Swapping the brain changes how the four stages reason and nothing
else — which is the whole claim the architecture makes, so it is worth it being
literally true rather than approximately true.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

# Model routing — cost engineering, which W15 calls the FDE's hidden
# deliverable. The cheap model does the high-volume stages; the expensive one
# touches exactly one step, the one where money moves.
#
# Overridable by env so the leaderboard's $5 ceiling can be defended by
# measurement rather than by argument.
MODEL_FAST = os.environ.get(
    "CLAIMSENSE_MODEL_FAST",
    "bedrock/converse/us.anthropic.claude-haiku-4-5-20251001-v1:0")
MODEL_SMART = os.environ.get(
    "CLAIMSENSE_MODEL_SMART",
    "bedrock/converse/us.anthropic.claude-sonnet-4-5-20250929-v1:0")

# Which stage gets which model. Coverage is the money step and the only one
# that concludes on cover, so it is the only one that earns the smart model.
STAGE_MODEL = {
    "triage": MODEL_FAST,
    "evidence": MODEL_FAST,
    "coverage": MODEL_SMART,
    "risk": MODEL_FAST,
    "adjudicator": MODEL_FAST,
}


@dataclass
class BrainConfig:
    mode: str           # mock | llm
    provider: str       # none | bedrock | openai
    fast: str | None = None
    smart: str | None = None

    @property
    def is_mock(self) -> bool:
        return self.mode == "mock"

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
                           fast=MODEL_FAST, smart=MODEL_SMART)
    if os.environ.get("OPENAI_API_KEY"):
        model = os.environ.get("CLAIMSENSE_MODEL", "gpt-5.4-mini")
        return BrainConfig(mode="llm", provider="openai", fast=model, smart=model)

    return BrainConfig(mode="mock", provider="none")
