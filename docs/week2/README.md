# Week 2 — Statement of work, pricing and solution architecture

**Submission bundle.** Discovery turned into an engagement plan and a technical
design: what we will do, what it costs, what could go wrong, and how the system
is put together.

---

## Deliverables

| # | Deliverable | Where |
|---|---|---|
| 1 | Statement of work — scope, acceptance criteria, IP and data handling, five-week timeline | [`SOW.md`](SOW.md) |
| 2 | Architecture diagram — every data flow labelled, the deterministic/model boundary marked | [`architecture.svg`](architecture.svg) · [`ARCHITECTURE.md`](../ARCHITECTURE.md) |
| 3 | Pricing model with assumptions stated | [`PRICING.md`](PRICING.md) |
| 4 | Risk register — five risks with likelihood, impact and mitigation | [`RISK_REGISTER.md`](RISK_REGISTER.md) |
| 5 | Typed contracts for all three client systems, with idempotency rules | [`../CONTRACTS.md`](../CONTRACTS.md) · [`../openapi/`](../openapi/) |
| 6 | Synthetic data shapes for claims, policies and documents | [`DATA_SHAPES.md`](DATA_SHAPES.md) |

---

## Read the architecture as the target state

[`architecture.svg`](architecture.svg) and the value-stream map in
[`../week1/VALUE_STREAMS.md`](../week1/VALUE_STREAMS.md) describe the end state
**after Week 4 integration** — value stream → stage → workflow → role → value
recipient, with ClaimSense inside Northwind's workflow.

Week 3 delivers the capability **standalone**: no portal integration and no
MCP. That is a scope boundary, not a gap — read this week's design as the
target, which is what Week 2 is for, rather than as a statement of what Week 3
ships. The boundary is enumerated under *Not in Week 3 scope* in
[`../week3/README.md`](../week3/README.md).

## The decision that shapes the architecture

Deterministic operations stay in code; model judgment is used where
interpretation is required. The architecture **makes that visible rather than
leaving it implicit**, which is the week's stated objective.

| Deterministic | Model judgment |
|---|---|
| identity, access control, who may confirm | reading the file: the FNOL, the notes, the documents |
| policy dates: in force, lapse, reporting window | which clause governs — must cite retrieved ids |
| money: deductible, limits, coinsurance, settlement | what the fraud indicators amount to together |
| the fraud **score** arithmetic | the drafted decision and its rationale |

It is enforced, not described. `agent/tests/test_boundary.py` walks the AST of
every module under `determinism/` and fails the build if one imports an agent
SDK, `litellm` or `boto3` — or if the money module grows a float literal.

Three cases make the line concrete:

- **Claim 4410** reads as an ordinary approvable kitchen fire. The loss is one
  day before inception. Date arithmetic denies it; no reading of the words could.
- **Claim 4411** is *exactly* the coverage limit. `>` versus `>=` is a one-cent
  difference on every capped claim in the book.
- **Claim 4405** has a plausible, sympathetic narrative. Four indicators sum
  past the threshold, and the model cannot talk the score down.

---

## Contracts, in one line each

Three systems, three credentials. A key scoped to one is refused by the others
with **403**, not 401 — the caller authenticated, they are at the wrong door.

| System | Writes | Rule worth knowing |
|---|---|---|
| **CMS** | the recommendation, and the adjuster's confirmation | a model-sourced `APPROVE` or `DENY` with no citation is **refused by the contract** |
| **PAS** | none | **no write contract exists** — an automated adjudicator that could alter a policy could manufacture the cover it then finds |
| **DMS** | a request for a missing document | poisoned documents are returned **flagged, not filtered** |

**Idempotency on every write.** A replay with the same key and body returns the
original record; the same key with a *different* body is a **409**. Returning
the first response would silently discard the second intent — an adjuster who
confirmed `APPROVE`, changed to `DENY` and reused the key would be told their
denial succeeded while the approval stood.

A duplicated claim decision is a duplicated payment. This is correctness, not
convenience.

---

## Still open

Every document here carries **NEEDS OWNER** markers where a decision rests on
client context rather than on the system — the day rate, the inference region,
the audit retention period, and each risk owner's acceptance of the scoring.

The thresholds in the SoW's acceptance criteria are proposed from discovery and
need each accountable stakeholder's sign-off before signature.
