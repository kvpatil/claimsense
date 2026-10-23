# Value streams and workflows — Northwind Mutual

Where the work actually flows, who is in each step, and which parts of it
ClaimSense automates.

Written in value-stream terms deliberately. "Automate claims" is not a scope;
"automate steps 2–5 of the settlement stream, leave 1, 6 and 7 human" is.

> Acronyms are expanded in [`../GLOSSARY.md`](../GLOSSARY.md).
> **CMS** Claims Management System · **PAS** Policy Administration System ·
> **DMS** Document Management System · **FNOL** First Notice of Loss ·
> **SIU** Special Investigations Unit · **ACV** Actual Cash Value

---

## The three value streams

A value stream is the end-to-end sequence that delivers something a customer
values. Northwind's claims operation runs three, and they are not variants of
each other — different triggers, different customers, different definitions of
done.

| | Value stream | Trigger | Customer | Value delivered | Done when |
|---|---|---|---|---|---|
| **VS1** | **Claim Settlement** | a loss is reported | the policyholder | a correct decision, fast | the claim is decided and paid or denied |
| **VS2** | **Fraud Management** | indicators cross a threshold | the premium pool | claims that should not be paid are not | SIU reports and the claim returns or closes |
| **VS3** | **Recovery (Subrogation)** | a claim is paid where a third party was at fault | the premium pool | money back | recovery is obtained or abandoned |

**VS1 is the engagement.** VS2 is touched only at its entry point — ClaimSense
decides *whether to refer*, never what the investigation concludes. VS3 is out
of scope: it begins after a claim is paid, and nothing in this pilot reaches it.

---

## VS1 — Claim Settlement

### The workflow chain

```
W1 Intake   →  W2 Coverage  →  W3 Evidence  →  W4 Valuation
                                                    ↓
            W7 Communicate ←  W6 Authorise  ←  W5 Adjudicate
                                   │
                   (W4a Total loss ─┘ when damage ≥ 75% of ACV)
                                   │
                   (→ VS2 Fraud  ───┘ when score ≥ 70)
```

### Who participates, step by step

**R** does the work · **A** owns the outcome · **C** is consulted · **I** is told

| | Workflow | intake | adjuster | senior adj. | supervisor | appraiser | SIU | subrogation |
|---|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| **W1** | Intake — capture the FNOL, open the claim | **R/A** | I | | | | | |
| **W2** | Coverage — was the policy in force, what does it cover | | **R/A** | C | C | | | |
| **W3** | Evidence — assemble the file across CMS, PAS, DMS | | **R/A** | | | C | C | |
| **W4** | Valuation — what is the loss worth | | **R** | C | | C | | |
| **W4a** | Total loss — value a written-off item | | C | | | **R/A** | | |
| **W5** | Adjudicate — reach one of four outcomes | | **R/A** | **R/A** | **R/A** | | | |
| **W6** | Authorise — settle within authority, or escalate | | **R** ≤$25k | **R** ≤$100k | **A** any | | | |
| **W7** | Communicate — the decision letter to the claimant | | **R/A** | | C | | | I |

Four of the seven desks appear as **R/A** on exactly one workflow or none.
That is the shape of the problem: the work is specialised, and nothing routes
it.

### Where the time goes today

Classic value-stream distinction: **process time** is work actually being done;
**lead time** is wall-clock including the waiting. The gap between them is the
waste.

| Workflow | Systems touched | Process time | Lead time | The gap is |
|---|---|---|---|---|
| W1 Intake | CMS | minutes | minutes | — |
| W2 Coverage | **PAS** | minutes | **queue wait** | waiting for an adjuster to open the file |
| W3 Evidence | **CMS + PAS + DMS** | the bulk of it | queue wait | three systems, by hand |
| W4 Valuation | DMS + PAS | minutes | queue wait | — |
| W4a Total loss | PAS | minutes | **re-queue** | a *second* desk, from a standing start |
| W5 Adjudicate | policy wording | the judgment | — | finding the clause |
| W6 Authorise | — | seconds | **re-queue** | a *third* desk, if over authority |
| W7 Communicate | CMS | minutes | — | — |

> **NEEDS OWNER** — the process and lead times above are shape, not
> measurement. Real figures come from a time study with the Lead Adjuster in
> week 1, and the four success criteria are calibrated against that baseline.
> They are deliberately left as descriptions rather than invented numbers.

### What the data already shows

Measured against the seeded queue, not estimated:

| | | Means |
|---|---|---|
| **62** claims | in the queue | — |
| **56** | already past 25 days | the decision clock is running on 90% of the book |
| **27** | over an adjuster's $25,000 authority | **44% need W6 escalation** — a second desk |
| **10** | total losses (damage ≥ 75% of ACV) | **16% need W4a** — an appraiser |
| **2** | fraud score ≥ 70 | leave VS1 for VS2 entirely |
| **12** | with no documents at all | cannot clear W3 without a request to the claimant |

**Roughly half of all claims need a desk beyond the first one.** Nothing in
the current system works that out — an adjuster opens the file, does the W2–W5
reading, and only then discovers they cannot finish it.

That is the single most expensive fact in this document. The handoff is not
the cost; the **work done before discovering the handoff** is.

---

## VS2 — Fraud Management

| | Workflow | adjuster | SIU | supervisor |
|---|---|:--:|:--:|:--:|
| **F1** | Detect — indicators recorded by upstream systems | I | **A** | |
| **F2** | Refer — score crosses the threshold | **R** | **A** | I |
| **F3** | Investigate | C | **R/A** | I |
| **F4** | Dispose — return to VS1, or close as fraud | I | **R** | **A** |

SIU **investigates; it does not adjudicate**. A referral is an invitation to
look, not a finding — which is why the SIU seat holds no adjuster licence and
cannot confirm a decision even on a claim it is working.

**ClaimSense participates in F2 only.** It decides whether the threshold is
crossed. It has no view on F3 or F4 and should never be given one.

---

## VS3 — Recovery (Subrogation)

| | Workflow | subrogation | supervisor |
|---|---|:--:|:--:|
| **S1** | Identify a recoverable claim | **R/A** | I |
| **S2** | Pursue the at-fault party | **R/A** | C |
| **S3** | Recover or abandon | **R** | **A** |

**Out of scope.** It starts after VS1 completes. Named here because a value
stream nobody drew is a value stream somebody assumes you covered.

---

## Where ClaimSense lands

```
W1 Intake      ░░░░  human — the claimant talks to a person
W2 Coverage    ████  AUTOMATED
W3 Evidence    ████  AUTOMATED
W4 Valuation   ████  AUTOMATED
W4a Total loss ▒▒▒▒  ROUTED to an appraiser, not performed
W5 Adjudicate  ████  AUTOMATED — produces a recommendation
W6 Authorise   ▒▒▒▒  ROUTED — the ladder is computed, the decision is human
W7 Communicate ▓▓▓▓  DRAFTED — a licensed adjuster confirms before it is sent
```

| | What ClaimSense does |
|---|---|
| **W2 · W3 · W4** | performed end to end — reads all three systems, establishes cover, assembles the file, computes what is payable |
| **W5** | performed — reaches one of four outcomes with the governing clause cited |
| **W4a · W6** | **computed, not performed** — which desk the claim needs is arithmetic, and ClaimSense works it out *before* anyone opens the file |
| **W7** | drafted only — nothing reaches a claimant unconfirmed |
| **W1** | untouched |
| **F3 · F4 · VS3** | untouched |

### The claim this makes

The automation is not "faster adjusters". It is that **W4a and W6 routing move
to the front of the stream**. Today they are discovered at the end, after the
reading is done, by the wrong person. Afterwards they are known before the
file is opened.

That is why the routing rules are deterministic and sit in
`agent/src/claimsense_agent/determinism/authority.py`. If they were model
judgment they could not be trusted to run first.

### What stays human, and why

| | Why |
|---|---|
| **W1 Intake** | a person in distress is talking to a person |
| **W5 confirmation** | the law reserves the decision for a licensed adjuster |
| **W6 authorisation** | the ladder is computed; the signature is not |
| **F3 Investigation** | SIU's judgment, informed by nothing we produce |

---

## Opportunities this surfaces, beyond the pilot

Named because a value-stream map that only confirms the planned scope was not
worth drawing.

| | Workflow | Why it is not in the pilot |
|---|---|---|
| Document request chasing | W3 | ClaimSense raises the first request; nothing chases. 12 claims sit with no documents. |
| Reserve setting | W4 | Reserves are set at intake and rarely revisited. Out of scope, and a real cost. |
| Subrogation identification | VS3 · S1 | The evidence to spot a recoverable claim is assembled in W3 and then discarded. |
| Total-loss valuation | W4a | ClaimSense routes to an appraiser; it does not value. Vehicle valuation is a different data problem. |

**NEEDS OWNER** — this map is drawn from the system and the brief. It should
be walked with the Lead Adjuster and the Claims Operations Manager and
corrected where the real process differs. A value stream map nobody who does
the work has reviewed is a diagram, not a finding.
