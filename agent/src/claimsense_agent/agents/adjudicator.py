"""Stage 4 — Adjudicate. One of four outcomes, and the reason for it.

This stage COMBINES; it does not re-decide. Coverage has already found covered
or excluded, risk has already been scored against a fixed threshold, and
eligibility and the settlement are arithmetic that happened before this ran.
What is left is precedence — which of several true things governs — and the
drafted explanation.

Precedence is fixed and lives in code, because "a lapsed policy outranks a
sympathetic narrative" is a business rule the client owns, not something that
should vary with sampling.
"""
from __future__ import annotations

from typing import Any

from ..contracts import (ClaimVerdict, CoverageOpinion, DecisionBasis,
                         EvidenceBundle, RiskAssessment, TriageDecision)

INSTRUCTIONS = """\
You are the Adjudicating agent at ClaimSense. You produce the FIRST DECISION on \
a claim, which a licensed adjuster will confirm or override. You are not the \
decision-maker; you are the draft.

You receive a triage classification, an evidence summary, a coverage finding \
with its citations, and a fraud assessment. Produce exactly one outcome:

  APPROVE       cover is confirmed, the policy was in force, and nothing is \
outstanding
  DENY          an exclusion applies, or there was no cover in force
  MORE_INFO     the file cannot support a decision — name the missing documents
  SIU_REFERRAL  the fraud indicators cross the referral threshold

Precedence, applied in this order and not negotiable: no cover in force beats \
everything; a fraud referral beats a coverage finding; an exclusion beats a \
grant; missing evidence beats a favourable reading.

Carry the coverage agent's citations through verbatim. Do not add citations of \
your own and do not drop one.

Write the rationale for the claimant's adjuster, not for an engineer: three or \
four sentences, plain words, and state what the policy says and what happens \
next."""


def _ELIGIBILITY_CLAUSE(eligibility) -> str | None:
    """The general provision a no-cover denial rests on.

    Lapse and policy-period are different denials and read differently to a
    claimant: one says you stopped paying, the other says this happened outside
    your term. They get different clauses because they are different reasons.
    """
    if eligibility.lapsed_before_loss:
        return "ALL-GEN-2"          # Cancellation and Nonpayment
    if eligibility.loss_before_inception or eligibility.loss_after_expiry:
        return "ALL-GEN-1"          # Policy Period and Territory
    return None


def run(*, triage: TriageDecision, evidence: EvidenceBundle,
        coverage: CoverageOpinion, risk: RiskAssessment, eligibility,
        settlement, basis: list[DecisionBasis]) -> ClaimVerdict:
    claim_id = triage.claim_id
    cited = list(coverage.cited_clause_ids)
    settlement_cents = None
    requested: list[str] = []

    # Which KIND of reasoning produced the outcome. M2 requires a model verdict
    # to be distinguishable from a deterministic one, and the honest test is
    # not "did a model run" — one ran on every branch — but "could the model
    # have changed this answer?".
    #
    # A lapsed policy, an unresolvable policy id and a fraud score over
    # threshold are all settled before any stage reasons, and no reading of the
    # narrative moves them. Those are deterministic_fallback. A coverage
    # finding is the model's reading of the file and is genuinely its own, so
    # that is model.
    source = "model"

    # --- precedence, highest first ------------------------------------------
    if not eligibility.policy_resolved:
        outcome = "MORE_INFO"
        source = "deterministic_fallback"
        # No policy means no form, so there is nothing to cite. An empty list
        # is the honest answer; citing the coverage agent's grant here would
        # quote a form we never established applies.
        cited = []
        rationale = (
            "The policy this claim refers to could not be found in the policy "
            "administration system, so there is nothing to check cover against. "
            "This is a data problem rather than a coverage problem: the claim "
            "needs a correct policy number before it can be adjudicated.")
        requested = ["policy_identification"]

    elif not eligibility.in_force:
        outcome = "DENY"
        source = "deterministic_fallback"
        # Quote the provision that actually governs. The coverage agent's
        # grant is irrelevant to a policy that was not on risk, and a denial
        # letter citing the dwelling grant would be quoting the wrong clause
        # at a claimant — which is the kind of error that becomes a complaint.
        cited = [c for c in (_ELIGIBILITY_CLAUSE(eligibility),)
                 if c and c in coverage.retrieved_clause_ids]
        reason = "; ".join(eligibility.reasons)
        rationale = (
            f"There was no cover in force when this loss occurred. {reason.capitalize()}. "
            "Because the policy did not respond on the date of loss, the terms "
            "of the form are not reached and the claim is denied.")

    elif risk.refer_to_siu:
        # A referral decides nothing about cover, so it carries no citation.
        cited = []
        # The threshold referred it, not the interpretation. The risk agent's
        # words explain the referral; they did not cause it.
        outcome = "SIU_REFERRAL"
        source = "deterministic_fallback"
        rationale = (
            f"This claim is being referred to the Special Investigations Unit. "
            f"{risk.interpretation} The coverage position is not being decided "
            "now — SIU will complete its enquiries first, and the claimant "
            "should be kept informed that the claim remains open.")

    elif coverage.finding == "excluded":
        outcome = "DENY"
        rationale = (
            f"{coverage.statement} The loss itself is not in dispute; the policy "
            "simply does not respond to this cause of loss. The denial letter "
            "should quote the clause above and explain the appeal route.")

    elif evidence.missing_documents or coverage.finding == "indeterminate":
        outcome = "MORE_INFO"
        requested = list(evidence.missing_documents)
        if evidence.missing_documents:
            cited = []
        # Missing documents are a table lookup against the required set; an
        # indeterminate coverage finding is the model declining to conclude,
        # which IS its judgment.
        source = ("deterministic_fallback" if evidence.missing_documents
                  else "model")
        if requested:
            rationale = (
                "The file cannot support a decision yet. Missing: "
                + ", ".join(d.replace("_", " ") for d in requested)
                + ". Once those are on file the claim can be decided; the "
                "decision clock continues to run meanwhile.")
        else:
            rationale = (
                f"{coverage.statement} Without a clause that settles the point, "
                "a first decision would be a guess, and this claim should be "
                "read by a licensed adjuster against the full policy form.")

    else:
        outcome = "APPROVE"
        settlement_cents = settlement.payable_cents if settlement else None
        rationale = (
            f"{coverage.statement} "
            + (f"{settlement.explain().capitalize()}. " if settlement else "")
            + "Subject to the adjuster's confirmation, this claim can be settled.")

    # Risk that did not reach referral still belongs in the file — an adjuster
    # confirming an approval should see that two indicators were noted.
    if outcome != "SIU_REFERRAL" and risk.indicators and risk.band != "low":
        rationale += f" Fraud indicators noted ({risk.band} band): {risk.interpretation}"

    confidence = min(coverage.confidence, triage.confidence)
    if outcome == "MORE_INFO":
        confidence = min(confidence, 0.7)

    return ClaimVerdict(
        claim_id=claim_id,
        outcome=outcome,
        source=source,
        rationale=rationale,
        cited_clause_ids=cited,
        settlement_cents=settlement_cents,
        decision_basis=basis,
        confidence=round(confidence, 2),
        requested_documents=requested,
    )
