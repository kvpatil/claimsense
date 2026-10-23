"""Which desk must handle this claim. Arithmetic, not judgment.

A personal-lines claim does not belong to one person. It crosses desks, and
WHICH desks is decided by numbers:

  * a settlement above the deciding seat's authority goes to a higher one
  * damage at or above a share of the item's value is a total loss, and a
    total loss is valued by an appraiser rather than repaired by an adjuster
  * a fraud score over the referral threshold goes to the investigations unit

All three are comparisons. None of them is a reading of the file, and none of
them may move because a narrative was persuasive — which is exactly why they
live here and not in a prompt.

The distinction worth holding on to: routing decides WHO handles the claim,
the coverage stages decide WHAT the outcome is. They are independent. Claim
4418 is a total loss AND excluded — it would route to appraisal if there were
anything to appraise, and the exclusion settles it regardless.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Share of actual cash value at which an item is written off rather than
# repaired. Real thresholds are set by state statute and by carrier policy and
# commonly sit between 70% and 80%; 75% is the middle of that band.
#
# A constant rather than a model's opinion because it is a business rule the
# client owns, and it has to be auditable and changeable without a prompt edit.
TOTAL_LOSS_RATIO = 0.75

# Per-state statutory thresholds override the default. Empty by design:
# inventing fifty states' total-loss formulas would be fabrication dressed as
# thoroughness. A real engagement fills this from counsel.
STATE_TOTAL_LOSS: dict[str, float] = {}

# Desks, in escalating settlement authority. Seats that do not adjudicate are
# not on this ladder at all.
AUTHORITY_LADDER = ("adjuster", "senior_adjuster", "supervisor")

# Roles whose authority is unbounded. Stored as NULL in the database, which is
# the same NULL a seat with NO authority carries — so the two are told apart
# by ROLE here rather than by the column, which cannot distinguish them.
UNLIMITED = {"supervisor"}

# Desks that handle a claim without ever deciding it.
NON_ADJUDICATING = {"intake", "siu", "appraiser", "subrogation"}


def _a(role: str) -> str:
    """'an adjuster', 'a supervisor'. These strings reach a claimant's file.

    Worth the three lines: the rationale is read by people, and "a adjuster"
    in a decision letter is the kind of thing that makes a careful reader
    wonder what else was not checked.
    """
    article = "an" if role[:1].lower() in "aeiou" else "a"
    return f"{article} {role.replace('_', ' ')}"


@dataclass
class TotalLoss:
    applicable: bool
    is_total_loss: bool
    ratio: float | None
    threshold: float
    reason: str


def total_loss(claimed_cents: int, acv_cents: int | None, state: str = "") -> TotalLoss:
    """Is the item written off rather than repaired?

    `acv_cents` is None for a liability claim — nothing of the insured's was
    damaged — and the test simply does not apply. That is a third answer, not
    a False, and collapsing it into False would report "repairable" about a
    claim with no item in it.
    """
    threshold = STATE_TOTAL_LOSS.get(state, TOTAL_LOSS_RATIO)

    if not acv_cents:
        return TotalLoss(False, False, None, threshold,
                         "no insured property to value — the total-loss test "
                         "does not apply")

    ratio = claimed_cents / acv_cents
    if ratio >= threshold:
        return TotalLoss(
            True, True, ratio, threshold,
            f"damage is {ratio:.0%} of the ${acv_cents / 100:,.0f} actual cash "
            f"value, at or above the {threshold:.0%} total-loss threshold")
    return TotalLoss(
        True, False, ratio, threshold,
        f"damage is {ratio:.0%} of actual cash value, under the "
        f"{threshold:.0%} threshold — repairable")


@dataclass
class Authority:
    seat_role: str
    limit_cents: int | None       # None = unlimited, or none at all
    unlimited: bool
    may_settle: bool
    within_authority: bool
    reason: str


def settlement_authority(adjuster: dict | None, settlement_cents: int | None) -> Authority:
    """May this seat settle this amount?"""
    if not adjuster:
        return Authority("none", None, False, False, False,
                         "no seat assigned to this claim")

    role = adjuster.get("role", "")
    limit = adjuster.get("authority_limit_cents")

    if role in UNLIMITED:
        return Authority(role, None, True, True, True,
                         f"{_a(role)} settles without a ceiling".capitalize())

    if role in NON_ADJUDICATING or limit is None:
        return Authority(role, None, False, False, False,
                         f"{_a(role)} seat holds no settlement authority".capitalize())

    if settlement_cents is None:
        # Nothing is being paid, so there is no amount to be over.
        return Authority(role, limit, False, True, True,
                         f"no settlement to authorise")

    if settlement_cents <= limit:
        return Authority(role, limit, False, True, True,
                         f"${settlement_cents / 100:,.0f} is within the "
                         f"${limit / 100:,.0f} authority of {_a(role)}")

    return Authority(role, limit, False, True, False,
                     f"${settlement_cents / 100:,.0f} exceeds the "
                     f"${limit / 100:,.0f} authority of {_a(role)}")


def next_authority(role: str) -> str | None:
    """The desk above this one on the ladder."""
    try:
        i = AUTHORITY_LADDER.index(role)
    except ValueError:
        return AUTHORITY_LADDER[0]
    return AUTHORITY_LADDER[i + 1] if i + 1 < len(AUTHORITY_LADDER) else None


@dataclass
class Routing:
    desk: str
    reason: str
    # Every desk the claim must cross, in order, including the one it is on.
    # The chain is the point: Week 1's cost is the handoffs, not the thinking.
    chain: list[str] = field(default_factory=list)
    escalated: bool = False


def route(*, adjuster: dict | None, outcome: str, settlement_cents: int | None,
          tl: TotalLoss, refer_to_siu: bool) -> Routing:
    """Which desk must handle this claim next, and why.

    Precedence is fixed and is NOT the same as the coverage precedence. A
    fraud referral outranks everything because the claim stops being
    adjudicated until the unit reports; a total loss outranks authority
    because it has to be valued before there is an amount to authorise.
    """
    chain = ["intake"]
    role = (adjuster or {}).get("role", "adjuster")
    if role not in NON_ADJUDICATING:
        chain.append(role)
    else:
        chain.append("adjuster")

    if refer_to_siu:
        chain.append("siu")
        return Routing("siu",
                       "fraud score crossed the referral threshold — the claim "
                       "is not adjudicated until the unit reports",
                       chain, escalated=True)

    if outcome == "APPROVE" and tl.is_total_loss:
        chain.append("appraiser")
        auth = settlement_authority(adjuster, settlement_cents)
        if not auth.within_authority:
            nxt = next_authority(auth.seat_role) or "supervisor"
            chain.append(nxt)
        return Routing("appraiser",
                       f"total loss — {tl.reason}. The item is valued by an "
                       "appraiser before any settlement is authorised",
                       chain, escalated=True)

    if outcome == "APPROVE":
        auth = settlement_authority(adjuster, settlement_cents)
        if not auth.within_authority:
            nxt = next_authority(auth.seat_role) or "supervisor"
            chain.append(nxt)
            return Routing(nxt, auth.reason + f" — escalated to {_a(nxt)}",
                           chain, escalated=True)
        return Routing(auth.seat_role, auth.reason, chain)

    # Denials, requests for information and referrals move no money, so
    # authority does not engage. The deciding seat keeps the claim.
    decided_by = role if role not in NON_ADJUDICATING else "adjuster"
    return Routing(decided_by,
                   f"no settlement is being authorised — {_a(decided_by)} "
                   "completes the claim", chain)
