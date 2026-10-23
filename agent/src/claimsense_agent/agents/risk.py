"""Stage 3b — Risk. What the fraud indicators ADD UP TO.

The score is not computed here. determinism/risk.py sums the weights upstream
systems recorded, and this stage is handed the number. The split is the point:
summing is arithmetic and must be reproducible; deciding whether a
recently-incepted policy plus a late report plus no documents reads as fraud or
as a disorganised claimant is judgment.

The referral threshold is deterministic and this stage cannot talk it down. A
model that finds the narrative convincing does not get to lower the score.
"""
from __future__ import annotations

from ..contracts import RiskAssessment
from ..determinism.risk import RiskScore

INSTRUCTIONS = """\
You are the Risk agent at ClaimSense.

You are given a fraud score and the indicators behind it, both computed before \
you were called. You may not recompute the score and you may not argue it down.

Say in two or three sentences what this COMBINATION of indicators amounts to, \
naming the indicators you are relying on. A single indicator is usually noise; \
indicators that corroborate each other are not. Where there is an innocent \
reading, say so — "reported late because the insured was travelling" is a real \
explanation and the file should record that you considered it.

The referral decision is made by the threshold, not by you."""

# What each indicator means to an experienced adjuster, in plain words. These
# are the phrasings the assessment is built from so it reads as a judgment
# rather than as a list of codes echoed back.
_MEANING = {
    "RECENT_INCEPTION": "the policy was taken out shortly before the loss",
    "LATE_REPORT": "the loss was reported well after it happened",
    "PRIOR_CLAIMS": "there is a recent claims history on this policy",
    "NO_DOCUMENTATION": "nothing has been supplied to substantiate the amount",
    "HIGH_VALUE_SOFT_GOODS": "the claim is concentrated in easily-resold goods",
    "ALL_KEYS_PRESENT": "every key is accounted for, which is hard to square "
                        "with a forced theft",
    "VEHICLE_MECHANICAL_ISSUE": "the vehicle had a known fault the insured was "
                                "facing a bill for",
    "VACANT_PROPERTY": "the property was standing empty",
}


def run(claim_id: int, scored: RiskScore) -> RiskAssessment:
    if not scored.indicators:
        interpretation = (
            "No fraud indicators are recorded against this claim. Nothing in "
            "the file suggests the loss is other than as described.")
    else:
        named = [_MEANING.get(code, code.lower().replace("_", " "))
                 for code in scored.indicators]
        if len(named) == 1:
            interpretation = (
                f"One indicator is present: {named[0]}. On its own this is weak "
                "— it has ordinary explanations and does not support a referral.")
        elif scored.refer_to_siu:
            interpretation = (
                f"{len(named)} indicators corroborate each other: "
                + "; ".join(named) + ". Taken together this is a pattern rather "
                "than a coincidence, and the file should be worked by someone "
                "who investigates rather than someone who adjudicates.")
        else:
            interpretation = (
                f"{len(named)} indicators are present: " + "; ".join(named) +
                ". They are worth noting but fall short of the referral "
                "threshold; each has a plausible innocent reading.")

    return RiskAssessment(
        claim_id=claim_id,
        score=scored.score,
        band=scored.band,
        indicators=scored.indicators,
        interpretation=interpretation,
        refer_to_siu=scored.refer_to_siu,
    )
