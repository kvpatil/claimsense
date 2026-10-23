"""Is there cover at all? Dates, lapse, and the reporting window.

This runs BEFORE any question of what the policy says, because if the policy
was not in force on the date of loss then no clause matters. It is pure date
comparison, which is why it is here and not in a prompt — ADV-02 is a loss one
day before inception, and a model reading the claimant's narrative would
cheerfully approve it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

# How long after a loss a claim can be reported before the policy's prompt-notice
# condition is arguable. Not a hard bar — late notice is a reason to look, not a
# reason to deny on its own — so it surfaces as a flag, not a verdict.
PROMPT_NOTICE_DAYS = 30


@dataclass
class Eligibility:
    policy_resolved: bool
    in_force: bool
    reasons: list[str] = field(default_factory=list)
    # Set when the policy exists but cover had already ceased. Distinct from
    # `in_force=False` for a loss outside the term: lapse is non-payment and
    # reads differently to the claimant.
    lapsed_before_loss: bool = False
    loss_before_inception: bool = False
    loss_after_expiry: bool = False
    late_notice_days: int = 0
    prompt_notice_flag: bool = False

    @property
    def blocks_coverage(self) -> bool:
        """True when no clause can rescue this claim."""
        return not self.policy_resolved or not self.in_force


def _d(value) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    return date.fromisoformat(str(value)[:10])


def check(policy: dict | None, date_of_loss, reported_at) -> Eligibility:
    """Whether cover was in force when the loss happened.

    `policy` is None when PAS has no record for the id the claim carries. That
    is reachable in production — the claim/policy reference crosses a vendor
    boundary with no foreign key behind it — so it returns an unresolved result
    rather than raising. ADV-04 exercises exactly this.
    """
    if policy is None:
        return Eligibility(
            policy_resolved=False, in_force=False,
            reasons=["policy not found in the policy administration system"],
        )

    dol = _d(date_of_loss)
    eff = _d(policy["effective_date"])
    exp = _d(policy["expiration_date"])
    lapse = _d(policy["lapse_date"]) if policy.get("lapse_date") else None

    e = Eligibility(policy_resolved=True, in_force=True)

    if dol < eff:
        e.in_force = False
        e.loss_before_inception = True
        e.reasons.append(
            f"date of loss {dol} precedes policy inception {eff}")
    # Expiry is exclusive: cover ends AT 12:01am on the expiration date, so a
    # loss on the expiration date itself is outside the term.
    if dol >= exp:
        e.in_force = False
        e.loss_after_expiry = True
        e.reasons.append(f"date of loss {dol} is on or after expiry {exp}")
    if lapse and dol >= lapse:
        e.in_force = False
        e.lapsed_before_loss = True
        e.reasons.append(
            f"policy lapsed {lapse} for non-payment; loss {dol} is after lapse")

    reported = _d(reported_at)
    e.late_notice_days = max(0, (reported - dol).days)
    e.prompt_notice_flag = e.late_notice_days > PROMPT_NOTICE_DAYS
    if e.prompt_notice_flag:
        e.reasons.append(
            f"reported {e.late_notice_days} days after the loss "
            f"(prompt-notice condition engages past {PROMPT_NOTICE_DAYS})")

    return e
