"""Identity and access control. Enforced in code, never by the model.

W14's architecture slide states the rule the client's CISO is buying: RBAC is
enforced in the deterministic layer, never in the LLM. A model asked whether a
seat may see a claim will answer plausibly and occasionally wrongly, and
"plausibly" is not a control.

Two distinct questions live here:
  * may this seat SEE this claim?            -> can_view
  * may this seat CONFIRM a decision on it?  -> can_confirm

They are separate because they have different answers. An SIU analyst can see
a referred claim they could never adjudicate, and a supervisor can see
everything. Confirming requires a LICENCE, which is a property of the person,
not of their role — cms.adjusters.license_number is NULL for the SIU seat
precisely so this is provable rather than asserted.
"""
from __future__ import annotations

from dataclasses import dataclass

SCOPE_ALL = "all"
SCOPE_STANDARD = "standard"
SCOPE_SIU = "siu"


@dataclass
class AccessDecision:
    allowed: bool
    reason: str

    def __bool__(self) -> bool:
        return self.allowed


def can_view(adjuster: dict | None, claim: dict, *, siu_referred: bool = False) -> AccessDecision:
    if not adjuster:
        return AccessDecision(False, "no authenticated seat")
    if not adjuster.get("active", True):
        return AccessDecision(False, "seat is deactivated")

    scope = adjuster.get("scope", SCOPE_STANDARD)
    if scope == SCOPE_ALL:
        return AccessDecision(True, "supervisor scope")
    if scope == SCOPE_SIU:
        if siu_referred:
            return AccessDecision(True, "SIU scope on a referred claim")
        return AccessDecision(False, "SIU scope is limited to referred claims")
    # Standard adjusters see what they are assigned. Unassigned claims are
    # visible to the queue, which is how work gets picked up.
    assigned = claim.get("assigned_adjuster_id")
    if assigned in (None, adjuster["adjuster_id"]):
        return AccessDecision(True, "assigned or unassigned claim")
    return AccessDecision(False, f"claim is assigned to adjuster {assigned}")


def can_confirm(adjuster: dict | None, claim: dict, *,
                siu_referred: bool = False) -> AccessDecision:
    """Confirming a decision is the act the whole system defers to a human.

    `siu_referred` has to be threaded through rather than defaulted away. It
    was missing at first, and the effect was subtle and bad: the SIU seat was
    refused at the VIEW check with "scope is limited to referred claims", so
    the licence check below — the control that actually matters — was
    unreachable for the one seat it exists to stop. The refusal looked correct
    and tested nothing.
    """
    view = can_view(adjuster, claim, siu_referred=siu_referred)
    if not view:
        return view
    if not adjuster.get("license_number"):
        return AccessDecision(
            False,
            f"seat {adjuster['adjuster_id']} holds no adjuster licence; "
            "only a licensed adjuster may confirm a decision")
    if adjuster.get("role") not in ("adjuster", "supervisor"):
        return AccessDecision(
            False, f"role '{adjuster.get('role')}' may not confirm decisions")
    return AccessDecision(True, f"licensed {adjuster['role']} "
                                f"({adjuster['license_number']})")
