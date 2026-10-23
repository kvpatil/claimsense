# Statement of Work

**Vendor** — *(engagement lead to complete)*
**Client** Northwind Mutual Insurance
**Engagement** ClaimSense — claims first-decision automation, pilot
**Version / date** v1.0 · 2026-10-15

---

## 1. Background and objectives

Northwind's adjusters decide first-instance personal-lines claims by hand,
assembling each file from three systems that do not talk to each other, then
reasoning to a decision with no support beyond the policy document and
experience. Two of the seven steps in that workflow — finding the clause that
governs, and computing what is payable — have no system behind them at all,
and that is where the inconsistency and the leakage come from.

The hard constraint is the statutory fair-claims clock: acknowledgement and a
decision are both due within fixed windows of a claim being reported, and
claims currently age toward those deadlines waiting for someone to open them.

This engagement automates the workflow up to, and not including, the decision.

## 2. Scope of work and deliverables

| Deliverable | Description | Milestone |
|---|---|---|
| Discovery and charter | current-state workflow, stakeholders, success criteria | M1 |
| Solution architecture | labelled data flows, the deterministic/model boundary, system contracts | M2 |
| Automated pipeline | four-stage agent set on the OpenAI Agents SDK, strict typed outputs | M3 |
| Policy retrieval | clause corpus search; every coverage conclusion cites the clauses actually retrieved | M3 |
| Guardrails | document quarantine, citation tripwire, determinism override, PII scan | M3 |
| Evaluation suite + CI gate | golden set with a pass threshold; a failing gate blocks the image push | M3 |
| Portal integration | recommendations surfaced in Claims Desk with a confirm/override control | M4 |
| Handover | runbook, evidence pack, decision record | M5 |

**Out of scope.** Commercial lines. Litigated or represented claims. Reserving
and reinsurance. Payment execution. Any autonomous decision — no outcome
reaches a claimant without a licensed adjuster confirming it.

## 3. Acceptance criteria

These are the Week 1 success criteria, copied in unchanged.

| Criterion | Metric | Threshold | Population |
|---|---|---|---|
| Decision accuracy | outcomes matching the Lead Adjuster's independent decision | **≥ 92%**, and **≥ 97%** where cover was not in force | 150-claim golden set, blind-reviewed |
| Pipeline latency | assignment to recommendation available | **p50 ≤ 60s · p95 ≤ 180s** | all claims worked in the pilot |
| Adjuster confirmation rate | confirmed without override | **≥ 80%** by week 4, **100%** of overrides carrying a reason | all recommendations reaching an adjuster |
| Fraud routing accuracy | SIU opens an investigation on the referral | **≥ 70% precision**, **≤ 5% miss rate** | all claims scored, reconciled with SIU |

**Acceptance is the Lead Adjuster's.** A pass rate is a number we can produce;
only a licensed adjuster can say the outcomes are right. If she will not sign,
the pilot does not proceed however green the gate is.

## 4. Timeline and milestones

| Milestone | Week | Gate | Sign-off |
|---|---|---|---|
| M1 — Discovery and charter | 1 | success criteria accepted by VP Claims | VP Claims |
| M2 — SoW, architecture, pricing | 2 | architecture accepted by CISO | CISO, VP Claims |
| M3 — Automated workflow in CI | 3 | eval gate ≥ 0.9, zero adversarial failures | Lead Adjuster |
| M4 — Integrated into Claims Desk | 4 | two-adjuster confirmation test passes | Lead Adjuster, IT |
| M5 — Prove and hand over | 5 | golden ≥ 0.95, evidence pack delivered | VP Claims, CISO |

## 5. Pricing and payment

Model: **fixed-price floor plus outcome component.** Full basis and
assumptions in [`PRICING.md`](PRICING.md).

| Item | Basis | Amount |
|---|---|---|
| Pilot fee | fixed, for the milestone set above | *(see PRICING.md)* |
| Outcome component | per claim decided within the fair-claims window at or above the accuracy threshold | *(see PRICING.md)* |

Payment schedule: 30% on M2 acceptance, 40% on M3, 30% on M5.

**Why this model.** Procurement gets a ceiling and the floor protects delivery
while system access resolves — the top risk in the register. The outcome
component is the alignment story for the board.

## 6. Intellectual property

| Artifact | Ownership |
|---|---|
| The pipeline, guardrails, evaluation harness, retrieval | **Vendor**, licensed to Client perpetually and irrevocably for internal use |
| Agent instructions and prompts | **Vendor**, same licence |
| Northwind claim, policy and document data | **Client**, at all times |
| The clause corpus and its identifiers | **Client** |
| Evaluation cases derived from Northwind claims | **Client**; Vendor may retain structural patterns with all Client data removed |
| Adjuster override reasons | **Client** |
| Derived artifacts — indexes, embeddings, fine-tunes | **Client**, deleted on termination, deletion certified |

No Client data is used to train or fine-tune any model. No Client data leaves
the agreed region.

## 7. Data handling

**Synthetic data only until the security review passes.** The pilot is built
and demonstrated entirely against generated data — same APIs, same identity
model, same audit path, never a real policyholder record. This is designed
for, not worked around: nothing in the build depends on production access.

| Data | Where it lives | Retention | Deletion | Subprocessors |
|---|---|---|---|---|
| Claims, FNOL, notes | Client CMS | per Client policy | Client-controlled | none |
| Policies, coverages, wording | Client PAS | per Client policy | Client-controlled | none |
| Documents and extracted text | Client DMS | per Client policy | Client-controlled | none |
| Recommendations and audit log | Client estate | *(NEEDS OWNER — Compliance)* | with the claim | none |
| Model inference | *(region NEEDS OWNER)* | **zero retention** | n/a | model provider only |

## 8. Security and compliance

- **Identity.** The automation acts as a named service seat with read scope
  across the queue and **no adjuster licence**, so it can never confirm its own
  recommendation. It is refused by the same check that refuses an SIU analyst.
- **Access control.** Enforced in the integration layer, never by the model.
  Credentials are scoped per client system; a key for one is refused by the
  others.
- **Audit.** Every request is logged with the acting identity, the resource and
  allow/deny. Denials are recorded as carefully as successes.
- **Idempotency.** Every write requires an `Idempotency-Key`. A duplicated
  claim decision is a duplicated payment.
- **Untrusted content.** Documents carrying instructions aimed at a model are
  quarantined before model context. The first notice of loss cannot be dropped
  — it is evidence — so it is fenced, and the citation tripwire makes a
  successful injection harmless.
- **Grounding.** Every coverage conclusion cites clauses actually retrieved. An
  uncited or fabricated citation blocks the output and routes to a human.

## 9. Change control

Scope changes are requested in writing, estimated and priced before work
starts. Changes affecting the acceptance criteria require the accountable
stakeholder's sign-off per the RACI.

## 10. Assumptions and dependencies

1. Read access to **non-production** instances of all three systems, with
   synthetic data, by end of week 2. *This is the critical path.*
2. The Lead Adjuster available two hours weekly to review outcomes and sign off
   decision quality.
3. The clause corpus supplied as text with stable identifiers.
4. SIU available at pilot end to reconcile referral accuracy.
5. Client-provided environments, credentials and network access.

## 11. Exit and offboarding

On termination: Client data and all derived artifacts deleted within 30 days,
deletion certified in writing; Vendor credentials revoked by Client; the
runbook, evidence pack and decision record handed over. Client retains the
perpetual licence in §6 to everything delivered and accepted.

## 12. Signatures

| | Name | Title | Date |
|---|---|---|---|
| Vendor | | | |
| Client | | | |

---

> **NEEDS OWNER** — amounts in §5 come from `PRICING.md` and need the VP's
> acceptance; the inference region and the audit retention period in §7 need
> Compliance; §12 needs both parties. Thresholds in §3 are proposed from
> discovery and need each accountable stakeholder's acceptance before signature.
