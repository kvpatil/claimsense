"""Unit tests for the deterministic layer — the answers that must not vary."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from claimsense_agent.determinism import clock, eligibility, identity, money, risk


# ---- money ----------------------------------------------------------------

def test_claim_exactly_at_the_limit_is_not_capped():
    """ADV-03. `>` and `>=` here differ by one cent on every capped claim."""
    s = money.settle(2_500_000, 2_500_000, 50_000)
    assert s.limit_applied is False
    assert s.payable_cents == 2_450_000


def test_one_cent_over_the_limit_is_capped():
    s = money.settle(2_500_001, 2_500_000, 50_000)
    assert s.limit_applied is True
    assert s.payable_cents == 2_450_000


def test_loss_under_the_deductible_pays_nothing():
    s = money.settle(80_000, 2_500_000, 100_000)
    assert s.payable_cents == 0
    assert s.fully_absorbed_by_deductible


def test_coinsurance_floors_rather_than_rounds_up():
    # 999 cents at 80% is 799.2 — paying 800 would pay a cent never owed.
    s = money.settle(claimed_cents=999 + 100, limit_cents=10_000,
                     deductible_cents=100, coinsurance_pct=80)
    assert s.payable_cents == 799


def test_settlement_is_always_an_integer():
    s = money.settle(1_234_567, 5_000_000, 100_000, 85)
    assert isinstance(s.payable_cents, int)


def test_negative_money_is_rejected():
    with pytest.raises(ValueError):
        money.settle(-1, 100, 0)


def test_governing_coverage_is_product_aware():
    covs = [{"coverage_code": "PP", "limit_cents": 1}, {"coverage_code": "DWELL", "limit_cents": 2}]
    assert money.governing_coverage("HO3", "fire", covs)["coverage_code"] == "DWELL"
    assert money.governing_coverage("HO3", "theft", covs)["coverage_code"] == "PP"
    # A renters form has no dwelling cover, so a structural peril has nowhere
    # to be paid from. None is the correct answer, not a failure.
    assert money.governing_coverage("HO4", "earthquake", covs) is None


# ---- eligibility ----------------------------------------------------------

POLICY = {"effective_date": "2026-01-08", "expiration_date": "2027-01-08",
          "lapse_date": None}


def test_loss_one_day_before_inception_is_not_covered():
    """ADV-02. Date arithmetic a sympathetic narrative cannot move."""
    e = eligibility.check(POLICY, "2026-01-07", "2026-01-09")
    assert e.in_force is False
    assert e.loss_before_inception is True


def test_loss_on_the_inception_date_is_covered():
    e = eligibility.check(POLICY, "2026-01-08", "2026-01-09")
    assert e.in_force is True


def test_loss_on_the_expiry_date_is_outside_the_term():
    """Cover ends AT 12:01am on the expiration date, so that day is out."""
    e = eligibility.check(POLICY, "2027-01-08", "2027-01-09")
    assert e.in_force is False
    assert e.loss_after_expiry is True


def test_lapse_beats_being_inside_the_term():
    lapsed = dict(POLICY, lapse_date="2026-08-24")
    e = eligibility.check(lapsed, "2026-09-23", "2026-09-24")
    assert e.in_force is False
    assert e.lapsed_before_loss is True


def test_missing_policy_is_reported_not_raised():
    """ADV-04. The claim/policy reference crosses a vendor boundary with no
    foreign key, so a dangling id is reachable in production."""
    e = eligibility.check(None, "2026-09-21", "2026-09-22")
    assert e.policy_resolved is False
    assert e.blocks_coverage is True


def test_late_notice_flags_but_does_not_deny():
    e = eligibility.check(POLICY, "2026-03-01", "2026-05-01")
    assert e.prompt_notice_flag is True
    assert e.in_force is True       # late notice is a reason to look, not to deny


# ---- risk -----------------------------------------------------------------

def test_single_indicator_does_not_refer():
    r = risk.score([{"indicator_code": "LATE_REPORT", "weight": 15, "detail": ""}])
    assert r.band == "low" and r.refer_to_siu is False


def test_stacked_indicators_cross_the_threshold():
    sig = [{"indicator_code": c, "weight": w, "detail": ""} for c, w in
           [("RECENT_INCEPTION", 25), ("LATE_REPORT", 15), ("PRIOR_CLAIMS", 20),
            ("NO_DOCUMENTATION", 20)]]
    r = risk.score(sig)
    assert r.score == 80 and r.band == "high" and r.refer_to_siu is True


def test_no_signals_scores_zero():
    assert risk.score([]).score == 0


# ---- identity -------------------------------------------------------------

ADJUSTER = {"adjuster_id": 1, "scope": "standard", "role": "adjuster",
            "license_number": "TX-ADJ-44190", "active": True}
SIU = {"adjuster_id": 4, "scope": "siu", "role": "siu",
       "license_number": None, "active": True}
SUPERVISOR = {"adjuster_id": 3, "scope": "all", "role": "supervisor",
              "license_number": "TX-ADJ-38104", "active": True}


def test_unlicensed_seat_cannot_confirm_even_when_it_can_view():
    """SIU can SEE a referred claim it could never adjudicate.

    Viewing and confirming are different questions with different answers, and
    the licence is a property of the person rather than of the role.
    """
    claim = {"assigned_adjuster_id": None}
    assert identity.can_view(SIU, claim, siu_referred=True).allowed is True
    decision = identity.can_confirm(SIU, claim, siu_referred=True)
    assert decision.allowed is False
    assert "licence" in decision.reason


def test_licensed_adjuster_can_confirm():
    assert identity.can_confirm(ADJUSTER, {"assigned_adjuster_id": 1}).allowed


def test_supervisor_sees_everything():
    assert identity.can_view(SUPERVISOR, {"assigned_adjuster_id": 999}).allowed


def test_adjuster_cannot_view_another_seats_claim():
    assert identity.can_view(ADJUSTER, {"assigned_adjuster_id": 2}).allowed is False


def test_siu_cannot_view_an_unreferred_claim():
    assert identity.can_view(SIU, {"assigned_adjuster_id": None},
                             siu_referred=False).allowed is False


def test_deactivated_seat_is_refused():
    assert identity.can_view(dict(ADJUSTER, active=False),
                             {"assigned_adjuster_id": 1}).allowed is False


# ---- clock ----------------------------------------------------------------

NOW = datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)


def test_clock_breaches_after_the_decision_window():
    ck = clock.compute("2026-07-01T10:00:00+00:00", now=NOW)
    assert ck.status == "BREACHED"
    assert ck.ack_breached is True


def test_fresh_claim_is_green():
    ck = clock.compute("2026-09-29T10:00:00+00:00", now=NOW)
    assert ck.status == "GREEN"
    assert ck.ack_breached is False


def test_naive_timestamp_is_treated_as_utc_not_rejected():
    ck = clock.compute("2026-09-29T10:00:00", now=NOW)
    assert ck.status == "GREEN"
