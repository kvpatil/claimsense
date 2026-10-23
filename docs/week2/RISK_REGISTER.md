# Risk register

Five risks, scored before mitigation. Likelihood and impact are **High /
Medium / Low**; exposure is the product.

> Ordered by exposure. The top one is not a technical risk, which is usually
> true and usually surprises people.

---

## R1 — System access is delayed by the security review

| | |
|---|---|
| **Likelihood** | **High** |
| **Impact** | **High** — M4 and M5 cannot start; the pilot cannot prove value on real claims |
| **Exposure** | **Critical** |
| **Owner** | CISO (accountable) · Engagement lead (managing) |

The CISO controls production data access and **does not report to the VP who
funds the pilot**. Either can stop rollout alone, and treating this as one
approval is how a pilot gets funded, built, and then parked.

**Mitigation.** Synthetic-only from day one — architectural, not a fallback.
M1–M3 complete with no client data at all, so a delayed review delays *proof*,
not *delivery*. The security questionnaire is answered structurally rather than
by promise: scoped per-system credentials, an audit row per request including
denials, idempotent writes, no model training on client data.
**10 days of standing time carried in the price** as the expected case.

**Residual.** Medium. The pilot still needs real claims eventually to make the
renewal case.

---

## R2 — Adjusters route around it

| | |
|---|---|
| **Likelihood** | **Medium** |
| **Impact** | **High** — a system nobody uses produces no benefit however accurate |
| **Exposure** | **High** |
| **Owner** | Lead Adjuster (accountable) · VP Claims |

Adjusters are measured on throughput. A tool that adds a review step they do
not trust gets bypassed, and a tool they cannot correct gets resented.

**Mitigation.** Confirming is one click; overriding takes three and requires a
reason. Every override becomes an evaluation case, so correcting the system is
*visibly* how it improves rather than a complaint into a void. The confirmation
rate is an acceptance criterion specifically because it measures adoption
rather than accuracy. The weekly outcome review with the Lead Adjuster is the
delivery mechanism, not a status meeting.

**Residual.** Medium. Adoption is behavioural and cannot be engineered away.

---

## R3 — A confidently wrong coverage decision reaches a claimant

| | |
|---|---|
| **Likelihood** | **Low** (post-mitigation) |
| **Impact** | **High** — regulatory exposure, complaint, and the engagement's credibility |
| **Exposure** | **High** |
| **Owner** | Compliance (accountable) · Vendor |

A model asserting cover it cannot ground is the failure mode that ends pilots.

**Mitigation.** Defence in depth, each layer tested so it can fail:
- every coverage conclusion must cite clauses **actually retrieved**; uncited
  or fabricated citations **block the output** and route to a human
- deterministic checks override the model on dates and money, and the verdict
  is re-stamped so the two are never confused
- every outcome is confirmed by a **licensed** adjuster before it reaches a
  claimant — enforced by a licence check, not by policy
- the eval gate tolerates **zero** adversarial regressions and blocks the image
  push

**Residual.** Low. The tripwire converts "confidently wrong" into "safely
escalated".

---

## R4 — Prompt injection through claim documents

| | |
|---|---|
| **Likelihood** | **Medium** — the inputs are attacker-influenceable by design |
| **Impact** | **Medium** — a manipulated outcome, caught at confirmation |
| **Exposure** | **Medium** |
| **Owner** | Vendor · CISO (informed) |

Claimants supply documents and write the first notice of loss. Both reach the
model, and both are text an attacker controls.

**Mitigation.** Documents carrying instructions are **dropped**, not sanitised
— stripping assumes the sanitiser caught every variant. The first notice of
loss **cannot** be dropped because it is evidence, so it is fenced as untrusted
content and the citation tripwire is what makes a successful injection
harmless. Two adversarial cases in the gate, both at zero tolerance.

**Residual.** Low-Medium. Quarantine has a cost and the system pays it: on one
case the poisoned file is the only estimate, so the claim becomes incomplete
rather than approved. An attacker cannot complete a claim file with a hostile
document.

---

## R5 — Retrieval misses the clause that governs

| | |
|---|---|
| **Likelihood** | **Medium** |
| **Impact** | **Medium** — an indeterminate outcome and an unnecessary human review |
| **Exposure** | **Medium** |
| **Owner** | Vendor |

Lexical retrieval scores on words, and a policy form is legal register while a
first notice of loss is written by someone whose house just flooded.

**Measured, not hypothesised.** The wear-and-tear exclusion scored *last of 25*
on a claim saying the roof "has been leaking" — the clause says "deterioration"
and "rot". Retrieving more results could never have fixed it.

**Mitigation.** Clauses carry the vocabulary **claimants** use alongside the
form's own. The governing grant for a product/peril is a structured lookup
rather than a ranked result, because grants never name perils. Product and
peril pre-filter the candidate set exactly.

**Residual.** Medium, and honestly so. A paraphrase none of that anticipates is
still missed — which produces `indeterminate` and a human review, never a
confident wrong answer. That is the trade: this risk degrades into R3's
mitigation rather than into a bad decision.

---

## Summary

| # | Risk | L | I | Exposure | Residual |
|---|---|---|---|---|---|
| R1 | Access delayed by security review | H | H | **Critical** | Medium |
| R2 | Adjusters route around it | M | H | **High** | Medium |
| R3 | Confidently wrong decision reaches a claimant | L | H | **High** | Low |
| R4 | Prompt injection through documents | M | M | **Medium** | Low-Med |
| R5 | Retrieval misses the governing clause | M | M | **Medium** | Medium |

**R1 and R2 are not technical and cannot be engineered away.** They are managed
through the commercial structure and the engagement cadence — which is why the
price carries a buffer and why the weekly outcome review is a deliverable
rather than a courtesy.

> **NEEDS OWNER** — each risk needs its named owner to accept the scoring and
> the mitigation before the SoW is signed.
