"""The fraud score. Arithmetic here; meaning is the model's job.

The split this module exists to make: SUMMING the weights an upstream system
recorded against a claim is deterministic and must be reproducible, so it
happens in code. Deciding what a particular combination of indicators ADDS UP
TO — whether a recently-incepted policy plus a late report plus no documents
looks like fraud or like a disorganised claimant — is judgment, and that lives
in the risk agent, which is handed this score and must name the indicators it
relied on.

Thresholds are constants rather than a model's opinion because the referral
boundary is a policy decision the client owns, and it has to be auditable and
changeable without a prompt edit.
"""
from __future__ import annotations

from dataclasses import dataclass, field

ELEVATED_AT = 40
HIGH_AT = 70
# Above this the claim goes to SIU regardless of how benign the narrative reads.
# A model that finds the story convincing cannot talk the score down.
REFER_AT = 70


@dataclass
class RiskScore:
    score: int
    band: str                       # low | elevated | high
    indicators: list[str] = field(default_factory=list)
    detail: list[str] = field(default_factory=list)
    refer_to_siu: bool = False


def score(signals: list[dict]) -> RiskScore:
    """Sum the recorded indicator weights. No interpretation."""
    total = sum(int(s.get("weight", 0)) for s in signals)
    codes = [s["indicator_code"] for s in signals]
    detail = [f"{s['indicator_code']} (+{s['weight']}): {s['detail']}"
              for s in signals]

    if total >= HIGH_AT:
        band = "high"
    elif total >= ELEVATED_AT:
        band = "elevated"
    else:
        band = "low"

    return RiskScore(score=total, band=band, indicators=codes, detail=detail,
                     refer_to_siu=total >= REFER_AT)
