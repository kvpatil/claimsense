# Engagement charter — Northwind Mutual

**Client** Northwind Mutual Insurance · personal lines (homeowners, renters, auto)
**Engagement** Claims first-decision automation — pilot
**Version** v1.0 · 2026-10-08

---

## 1. The problem, as the client states it

Northwind's adjusters decide first-instance property and auto claims by hand.
Working a single claim means assembling it from three systems that do not talk
to each other, then reasoning to a decision with no support beyond the policy
document and experience.

The cost shows up in four places, and the client named all four before we
proposed anything:

- **Throughput.** The queue grows faster than it is worked. Claims age toward
  the statutory decision deadline while waiting for someone to open them.
- **Consistency.** The same facts reach different adjusters and produce
  different outcomes. Nothing records which clause a decision rested on, so
  disagreements cannot be reconstructed.
- **Leakage.** Decisions made under time pressure pay claims the policy does
  not cover, and deny claims it does.
- **Fraud.** Indicators are recorded by upstream systems and read
  inconsistently. Referral to the Special Investigations Unit depends on
  whether the adjuster working the file notices the pattern.

> *"Three systems, three tabs, and no two adjusters find the clause the same
> way."* — Claims Operations Manager, discovery session 2

## 2. The current workflow

What an adjuster does today, per claim:

| Step | System | What it takes |
|---|---|---|
| Read the claim and the first notice of loss | Claims management | the claimant's account, in their words |
| Check cover was in force on the date of loss | Policy administration | effective/expiry dates, lapse status |
| Find the limit and deductible for the peril | Policy administration | which coverage section applies |
| See what has been supplied | Document store | and work out what is missing |
| Find the governing clause | **No system** | policy wording, searched by hand or recalled |
| Compute what is payable | **No system** | limit, deductible, coinsurance, by hand |
| Write the decision | Claims management | free text to the claimant |

Two of those seven steps have no system behind them at all. They are where the
inconsistency and the leakage come from.

## 3. The three client systems and their integration points

| System | Role | ClaimSense reads | ClaimSense writes |
|---|---|---|---|
| **Claims Management (CMS)** | system of record for the claim | claim, first notice of loss, adjuster notes, recorded fraud indicators | the recommendation, and the adjuster's confirmation |
| **Policy Administration (PAS)** | system of record for cover | policy, dates, status, coverages, limits, deductibles, the policy wording | **nothing — read-only by design** |
| **Document Store (DMS)** | the files on a claim | documents and extracted text, including the poisoned flag | a request for a missing document |

Three separate vendors, three separate contracts, three separate credentials.
There is no referential integrity between them: a claim can carry a policy
reference the policy system does not resolve, and the pilot must handle that
rather than assume it away.

**PAS is read-only and will stay so.** An automated adjudicator that could
alter a policy could manufacture the cover it then finds.

## 4. Scope of the pilot

**In scope.** First decisions on personal-lines property and auto claims,
producing one of four outcomes — approve, deny, request more information, or
refer to SIU — with the policy clauses the decision rests on cited and
recorded. The adjuster confirms every outcome.

**Out of scope for the pilot.** Commercial lines. Litigated and represented
claims. Reserving and reinsurance. Payment execution. Any autonomous decision:
nothing reaches a claimant without a licensed adjuster confirming it.

## 5. The constraint that shapes everything

Northwind's security review has not completed. Until it does:

> **Synthetic data only.** The pilot is built and demonstrated entirely against
> generated data. Same APIs, same identity model, same audit path — never a
> real policyholder record.

This is accepted and designed for, not worked around. Nothing in the build
depends on production access.

## 6. What success looks like

Four criteria, quantified, in [`SUCCESS_CRITERIA.md`](SUCCESS_CRITERIA.md).
They become the acceptance criteria of the statement of work verbatim.

## 7. How we will know

A golden evaluation set of claims spanning all four outcomes, including
adversarial cases, with a pass threshold enforced in continuous integration.
The initial twenty cases are in [`EVAL_CASES.md`](EVAL_CASES.md).

---

### Assumptions

1. Read access to non-production instances of all three systems, with
   synthetic data, by the end of week 2.
2. A named licensed adjuster available two hours per week to review outcomes.
3. The policy wording corpus can be supplied as text with stable clause
   identifiers.

### What would stop this

Access to the three systems is the critical path. Every week of delay is a
week the pilot cannot start, and this is the risk the SoW prices a buffer for.

---

**NEEDS OWNER** — the client contacts, the signature block, and the pilot
start date are for the engagement lead to complete. Stakeholder roles are
mapped in [`STAKEHOLDERS.md`](STAKEHOLDERS.md); the names there are
placeholders.
