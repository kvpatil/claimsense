"""Settlement authority, total loss, and which desk handles a claim.

All three are arithmetic, and all three decide WHO works the claim rather than
WHAT the answer is. That separation is the thing these tests pin down.
"""
from __future__ import annotations

import pytest

from claimsense_agent.determinism import authority as a

ADJUSTER = {"role": "adjuster", "authority_limit_cents": 2_500_000}
SENIOR = {"role": "senior_adjuster", "authority_limit_cents": 10_000_000}
SUPERVISOR = {"role": "supervisor", "authority_limit_cents": None}
SIU = {"role": "siu", "authority_limit_cents": None}
APPRAISER = {"role": "appraiser", "authority_limit_cents": None}
INTAKE = {"role": "intake", "authority_limit_cents": None}


# ---- total loss ----------------------------------------------------------

def test_damage_at_the_threshold_is_a_total_loss():
    """Exactly 75% is a total loss. `>` vs `>=` writes off a different car."""
    tl = a.total_loss(claimed_cents=750_000, acv_cents=1_000_000)
    assert tl.is_total_loss is True


def test_a_cent_under_the_threshold_is_repairable():
    tl = a.total_loss(claimed_cents=749_999, acv_cents=1_000_000)
    assert tl.is_total_loss is False


def test_damage_over_the_value_is_a_total_loss():
    tl = a.total_loss(claimed_cents=3_400_000, acv_cents=3_000_000)
    assert tl.is_total_loss is True
    assert tl.ratio > 1


def test_no_acv_means_the_test_does_not_apply():
    """A liability claim damages nothing of the insured's.

    Three answers, not two: 'not applicable' must not collapse into 'not a
    total loss', which would report "repairable" about a claim with no item.
    """
    tl = a.total_loss(claimed_cents=3_500_000, acv_cents=None)
    assert tl.applicable is False
    assert tl.is_total_loss is False
    assert "does not apply" in tl.reason


# ---- settlement authority ------------------------------------------------

def test_within_authority():
    auth = a.settlement_authority(ADJUSTER, 1_750_000)
    assert auth.within_authority is True


def test_at_the_authority_limit_exactly():
    """At the limit is within it. One cent over is not."""
    assert a.settlement_authority(ADJUSTER, 2_500_000).within_authority is True
    assert a.settlement_authority(ADJUSTER, 2_500_001).within_authority is False


def test_the_ladder_escalates_in_order():
    over = 4_200_000
    assert a.settlement_authority(ADJUSTER, over).within_authority is False
    assert a.settlement_authority(SENIOR, over).within_authority is True
    assert a.settlement_authority(SUPERVISOR, over).within_authority is True


def test_supervisor_is_unlimited_not_zero():
    """NULL on a supervisor means no ceiling; NULL on SIU means no authority.

    Same column, opposite meanings — told apart by role, because the column
    cannot distinguish them.
    """
    sup = a.settlement_authority(SUPERVISOR, 99_000_000)
    assert sup.may_settle is True and sup.unlimited is True
    siu = a.settlement_authority(SIU, 100)
    assert siu.may_settle is False and siu.unlimited is False


@pytest.mark.parametrize("seat", [SIU, APPRAISER, INTAKE])
def test_non_adjudicating_desks_hold_no_authority(seat):
    assert a.settlement_authority(seat, 100).may_settle is False


def test_no_settlement_needs_no_authority():
    """A denial moves no money, so there is no amount to be over."""
    assert a.settlement_authority(ADJUSTER, None).within_authority is True


def test_next_authority_walks_up_and_stops():
    assert a.next_authority("adjuster") == "senior_adjuster"
    assert a.next_authority("senior_adjuster") == "supervisor"
    assert a.next_authority("supervisor") is None


# ---- routing -------------------------------------------------------------

def route(outcome, settlement, tl, siu=False, seat=ADJUSTER):
    return a.route(adjuster=seat, outcome=outcome, settlement_cents=settlement,
                   tl=tl, refer_to_siu=siu)


REPAIRABLE = a.total_loss(940_000, 3_100_000)
WRITE_OFF = a.total_loss(2_380_000, 2_800_000)
NO_PROPERTY = a.total_loss(3_500_000, None)


def test_routine_approval_stays_with_the_adjuster():
    r = route("APPROVE", 1_750_000, REPAIRABLE)
    assert r.desk == "adjuster" and r.escalated is False


def test_approval_over_authority_escalates_up_the_ladder():
    r = route("APPROVE", 6_100_000, REPAIRABLE)
    assert r.desk == "senior_adjuster" and r.escalated is True
    assert r.chain == ["intake", "adjuster", "senior_adjuster"]


def test_covered_total_loss_goes_to_an_appraiser():
    r = route("APPROVE", 2_280_000, WRITE_OFF)
    assert r.desk == "appraiser"
    assert "valued by an appraiser" in r.reason


def test_fraud_referral_outranks_everything():
    """Even a total loss. The claim stops being adjudicated until SIU reports."""
    r = route("APPROVE", 2_280_000, WRITE_OFF, siu=True)
    assert r.desk == "siu"


def test_a_denial_does_not_escalate_however_large():
    """Routing and coverage are independent questions.

    Claim 4418 is a total loss AND excluded. There is nothing to appraise and
    no money to authorise, so the deciding seat completes it.
    """
    r = route("DENY", None, WRITE_OFF)
    assert r.desk == "adjuster" and r.escalated is False


def test_more_info_does_not_escalate():
    assert route("MORE_INFO", None, REPAIRABLE).escalated is False


def test_every_chain_starts_at_intake():
    for outcome, settle, tl in [("APPROVE", 1_000_000, REPAIRABLE),
                                ("APPROVE", 9_000_000, WRITE_OFF),
                                ("DENY", None, NO_PROPERTY)]:
        assert route(outcome, settle, tl).chain[0] == "intake"
