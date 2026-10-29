"""A verdict resting on a fallen-back stage is not a model verdict.

M2: "model-generated verdicts distinguishable from deterministic fallback
output". The adjudicator's precedence ladder already stamps
deterministic_fallback when CODE settled the outcome; this covers the other
route to the same label — the model was asked and could not answer.
"""
from __future__ import annotations

from claimsense_agent.agents import adjudicator
from claimsense_agent.contracts import (CoverageOpinion, EvidenceBundle,
                                        RiskAssessment, TriageDecision)
from claimsense_agent.determinism.eligibility import check as elig_check


def _parts():
    policy = {"product": "HO3", "status": "active",
              "effective_date": "2026-01-01", "expiration_date": "2027-01-01",
              "lapse_date": None}
    return dict(
        triage=TriageDecision(
            claim_id=1, peril="fire", product="HO3", severity="moderate",
            ack_due_at="2026-10-01", decision_due_at="2026-11-01",
            clock_status="GREEN", hours_to_decision_deadline=300.0,
            rationale="a fire loss", confidence=0.9),
        evidence=EvidenceBundle(
            claim_id=1, source_systems=["cms", "pas", "dms"], system_count=3,
            sufficient=True, facts=["f"], documents_on_file=["police_report"],
            missing_documents=[]),
        coverage=CoverageOpinion(
            claim_id=1, finding="covered", statement="Covered [HO3-I-A-1].",
            cited_clause_ids=["HO3-I-A-1"],
            retrieved_clause_ids=["HO3-I-A-1"], confidence=0.9),
        risk=RiskAssessment(claim_id=1, score=0, band="low", indicators=[],
                            interpretation="nothing noted", refer_to_siu=False),
        eligibility=elig_check(policy, "2026-06-01", "2026-06-02"),
        settlement=None, basis=[])


def test_a_clean_model_run_is_stamped_model():
    v = adjudicator.run(**_parts())
    assert v.outcome == "APPROVE"
    assert v.source == "model"


def test_a_fallen_back_stage_forces_deterministic_fallback():
    v = adjudicator.run(**_parts(), fell_back=["coverage"])
    assert v.outcome == "APPROVE"          # the outcome is unchanged...
    assert v.source == "deterministic_fallback"   # ...but it is not a model's


def test_any_fallen_back_stage_counts_not_just_coverage():
    for stage in ("triage", "evidence", "coverage"):
        v = adjudicator.run(**_parts(), fell_back=[stage])
        assert v.source == "deterministic_fallback", stage


def test_an_empty_fallback_list_changes_nothing():
    assert adjudicator.run(**_parts(), fell_back=[]).source == "model"
    assert adjudicator.run(**_parts(), fell_back=None).source == "model"
