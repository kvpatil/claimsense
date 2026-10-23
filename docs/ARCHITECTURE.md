# ClaimSense — solution architecture

Every data flow is labelled, and the boundary between deterministic code and
model judgment is marked explicitly rather than left implicit. That boundary is
the thing the client's security review is buying, so it is drawn here, enforced
in `agent/src/claimsense_agent/determinism/`, asserted in
`agent/tests/test_boundary.py`, and rendered in the console.

---

## The system

```
 ┌──────────────── CLIENT SYSTEMS (three vendors, three contracts) ─────────────┐
 │                                                                              │
 │   CMS                        PAS                        DMS                  │
 │   Claims Management          Policy Administration      Document Management  │
 │   System                     System                     System               │
 │   claims · FNOL · notes      policies · coverages       files · OCR text     │
 │   fraud signals · decisions  limits · clause corpus     poisoned flag        │
 │                                                                              │
 └──────┬──────────────────────────┬──────────────────────────┬─────────────────┘
        │ (1) read                 │ (2) read                 │ (3) read
        │ Bearer csk_cms_…         │ Bearer csk_pas_…         │ Bearer csk_dms_…
        ▼                          ▼                          ▼
 ╔══════════════════════ INTEGRATION LAYER (ours) ══════════════════════════════╗
 ║  authn · per-system scope · RBAC · idempotency · audit log                   ║
 ║                                                                              ║
 ║  RBAC IS ENFORCED HERE, NEVER IN THE MODEL.                                  ║
 ║  A model asked whether a seat may see a claim answers plausibly and          ║
 ║  occasionally wrongly, and "plausibly" is not a control.                     ║
 ╚══════┬═══════════════════════════════════════════════════════════╤═══════════╝
        │ (4) one claim bundle                                      │ (12) write
        ▼                                                           │  idempotent
 ┌─────────────────────── CLAIMSENSE PIPELINE ──────────────────┐   │  audited
 │                                                              │   │
 │  ▣ DETERMINISTIC — established BEFORE anything reasons       │   │
 │    (5) eligibility   in force? lapsed? loss inside the term? │   │
 │        clock         acknowledge / decide deadlines          │   │
 │        money         governing coverage, deductible, limit,  │   │
 │                      coinsurance → payable (integer cents)   │   │
 │        risk score    Σ indicator weights vs a fixed threshold│   │
 │        identity      which seat may see this, who may confirm│   │
 │                                                              │   │
 │  ══════════ THE BOUNDARY ══════════                          │   │
 │  Facts cross downward. Judgment never crosses back up.       │   │
 │                                                              │   │
 │  ◆ MODEL JUDGMENT — each stage returns a strict typed output │   │
 │    (6) Triage      peril, severity          ·  Haiku 4.5     │   │
 │         ➜ handoff                                            │   │
 │    (7) Evidence    what is on file, across 3 systems         │   │
 │         🛡 INPUT GUARDRAIL — quarantine poisoned documents   │   │
 │            dropped BEFORE model context. Fails closed.       │   │
 │         ➜ handoff                                            │   │
 │    (8) Coverage    which clause governs      ·  Sonnet 4.5   │   │
 │         ⌕ BM25 over the clause corpus  ──────────────────────┼───┘ (9) retrieve
 │         🛡 OUTPUT GUARDRAIL — citation tripwire              │
 │            cited ⊄ retrieved → BLOCKED → human               │
 │    (10) Risk       what the indicators amount to             │
 │    (11) Adjudicate one of four outcomes, fixed precedence    │
 │         🛡 determinism override → deterministic_fallback     │
 │         🛡 PII scan → synthetic-only invariant               │
 └──────────────────────────────┬───────────────────────────────┘
                                │ (13) recommendation, confirmed_by NULL
                                ▼
                    ┌───────────────────────────┐
                    │  ADJUSTER CONSOLE :3200   │
                    │  evidence · clauses ·     │
                    │  decision · confirm       │
                    └─────────────┬─────────────┘
                                  │ (14) a LICENSED adjuster confirms or overrides
                                  ▼
                        the claim becomes decided
```

### The flows

| # | Flow | Carries | Guarded by |
|---|---|---|---|
| 1 | Agent → CMS | claim, FNOL, notes, fraud signals | `csk_cms_…`, scope, audit |
| 2 | Agent → PAS | policy, coverages, clause corpus | `csk_pas_…`, read-only |
| 3 | Agent → DMS | documents + OCR text, `is_poisoned` | `csk_dms_…` |
| 4 | Integration → pipeline | one claim bundle | — |
| 5 | Deterministic facts | dates, money, score, access | **no model in the path** |
| 6–8, 10–11 | Stage outputs | strict typed dataclasses | output guardrails |
| 9 | Coverage → corpus | BM25 query + pre-filter | retrieval set is recorded |
| 12 | Pipeline → CMS | the recommendation | `Idempotency-Key`, audit |
| 13 | CMS → console | `confirmed_by IS NULL` | — |
| 14 | Adjuster → CMS | confirm or override | **licence required** |

---

## Where the boundary is, exactly

**Deterministic.** One correct answer, and it must not depend on sampling.

| Module | Owns |
|---|---|
| `determinism/identity.py` | who may view a claim; who may confirm a decision |
| `determinism/eligibility.py` | in force at date of loss, lapse, reporting window |
| `determinism/clock.py` | acknowledgement and decision deadlines |
| `determinism/money.py` | governing coverage, deductible, limit, coinsurance |
| `determinism/risk.py` | the fraud score and the referral threshold |

**Model judgment.** Interpretation, and every judgment names its evidence.

| Agent | Produces | Must carry |
|---|---|---|
| `agents/triage.py` | `TriageDecision` | peril, severity, confidence |
| `agents/evidence.py` | `EvidenceBundle` | systems answered, missing documents |
| `agents/coverage.py` | `CoverageOpinion` | `cited_clause_ids ⊆ retrieved_clause_ids` |
| `agents/risk.py` | `RiskAssessment` | the indicators it relied on, named |
| `agents/adjudicator.py` | `ClaimVerdict` | outcome, rationale, `source` |

### Why these, specifically

A settlement is arithmetic over a limit and a deductible. There is one right
answer and the claimant is entitled to it, so it is computed, not reasoned
about. Whether "water came up over the kerb" is a flood or a burst pipe is a
reading of the file — there is no formula, and that is what the model is for.

Three cases make the line concrete:

* **Claim 4410** — the narrative describes an ordinary kitchen fire and reads
  as approvable. The loss is one day before inception. Date arithmetic denies
  it; no reading of the words could.
* **Claim 4411** — the claim is *exactly* the coverage limit. `>` versus `>=`
  is a one-cent difference on every capped claim in the book.
* **Claim 4405** — the narrative is plausible and sympathetic. Four fraud
  indicators sum past the threshold, and the model cannot talk the score down.

---

## What the model never gets

* **It never computes a date, a deductible or a limit.** Those arrive as facts.
* **It never decides access.** `determinism/identity.py` and the integration
  layer do, before a stage runs.
* **It never sees a quarantined document.** The input guardrail drops it at the
  point of collection, where the drop can be logged.
* **It never writes.** The pipeline produces a recommendation; a licensed human
  confirms before anything is recorded as decided.

---

## Retrieval

BM25 over 46 clauses, local and deterministic. No embedding spend, no vector
store, and the same claim retrieves the same clauses on every run — an eval
that drifts gates nothing.

Two deterministic supports do work the ranker cannot:

* **Peril/product pre-filter.** An AUTO racing exclusion must *never* be
  retrieved for a homeowners water claim. `perils` and `product` are structured
  fields, so the filter is exact where scoring is fuzzy.
* **Pinned grants.** A grant of coverage never names a peril — `HO3-I-A-1`
  describes "the dwelling" and never says "fire" — so a fire claim cannot
  retrieve its own grant by lexical score. Which section grants cover for a
  (product, peril) is a structured fact, so it is looked up and pinned.

And one index-level fix. Clauses carry a `keywords` field holding the
vocabulary **claimants** use. A policy form is legal register; a first notice
of loss is written by someone whose house just flooded. Measured: the
wear-and-tear exclusion scored *last of 25* on a claim that said the roof "has
been leaking" and the ceiling was "sagging", because the clause says
"deterioration" and "rot" and the narrative says neither. With keywords it
ranks first. Retrieving more could never have fixed it.

**The honest limitation.** BM25 is lexical. A paraphrase the keywords do not
anticipate will still be missed. The citation tripwire is what makes that
survivable: a miss produces `indeterminate` and a human review, never a
confident wrong answer.

---

## Trust boundaries

| Boundary | Assumption | Control |
|---|---|---|
| Claimant → FNOL | hostile | fenced as untrusted; tripwire downstream |
| Claimant → documents | hostile | quarantine, fails closed |
| PAS clause corpus | trusted | read-only; no write contract exists |
| Agent → client systems | semi-trusted | per-system key, scope, audit, idempotency |
| Agent → decision | **never trusted to be final** | licensed human confirms |

The agent runs as a service seat (adjuster 5) with `scope='all'` and a **NULL
licence**. It reads any claim in the queue and can never confirm its own
recommendation — refused by the same check that refuses the SIU analyst.
Nothing in the code says "the agent may not confirm"; it simply has no licence,
and confirming requires one.

---

## Deployment

```
docker compose up
  ├── db      postgres:16, port 5433
  ├── seed    one-shot, idempotent by guard
  ├── web     console + the three APIs, :3200
  └── agent   a job, not a service (profile: agent)
```

CI builds and pushes both images only behind `needs: [test, eval, integration]`.
See [`DECISIONS.md`](../DECISIONS.md) for what was considered and rejected.
