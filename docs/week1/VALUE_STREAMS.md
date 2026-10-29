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

A value stream is the end-to-end sequence that delivers something someone
values. Northwind's claims operation runs three — different triggers,
different recipients, different definitions of done.

| | Value stream | Trigger | Done when |
|---|---|---|---|
| **VS1** | **Claim Settlement** | a loss is reported | the claim is decided, paid or denied, and closed |
| **VS2** | **Fraud Management** | indicators cross a threshold | SIU reports and the claim returns to VS1 or closes |
| **VS3** | **Recovery (Subrogation)** | a claim is paid where a third party was at fault | recovery is obtained or abandoned |

**VS1 is the engagement.** VS2 is touched only at its entry point —
ClaimSense decides *whether to refer*, never what the investigation concludes.
VS3 is out of scope: it begins after a claim is paid.

---

## What each stream actually produces, and for whom

The useful question is not "what value does this stream deliver" but **what
discrete items does it hand to which stakeholder**. One stream serves several
stakeholders, and they value different things about the same output.

Marked **⚠ not produced today** where the Week 1 system does not deliver the
item at all. Those gaps are the engagement.

### VS1 — Claim Settlement

| Value item | Goes to | Why they value it |
|---|---|---|
| **A coverage determination** — one of four outcomes | Policyholder | certainty; they can stop waiting and start rebuilding |
| | Insurer (VP Claims) | the liability is resolved and off the open book |
| **A settlement payment** — the indemnity, net of deductible | Policyholder | being made whole; this is what they bought |
| **A written rationale naming the governing clause** | Policyholder | *why* — especially on a denial, this is what makes it acceptable rather than arbitrary |
| | Compliance | a defensible decision if the regulator or a complaint asks |
| | Adjuster | something they can stand behind |
| | ⚠ **not produced today** | nothing records which clause a decision rested on |
| **A decision inside the statutory window** | Regulator | fair-claims compliance is a legal obligation, not a service level |
| | Policyholder | the clock is the only protection they have against being ignored |
| **An accurate reserve** — what this claim will cost | Finance | the liability on the books is a real number, not a placeholder |
| | ⚠ **weakly served today** | reserves are set at intake and rarely revisited |
| **A closed claim record** | Insurer | loss statistics that feed pricing |
| | Underwriting | what this book actually costs to insure |
| **Routing foreknowledge** — which desk this needs | Adjuster | not doing the reading before discovering you cannot finish |
| | ⚠ **not produced today** | 44% need a second desk and nothing works it out up front |

The policyholder is the **primary** stakeholder but not the only one, and the
items they care about are not the ones Finance or Compliance care about. A
stream optimised only for payment speed quietly stops producing the rationale
and the reserve.

### VS2 — Fraud Management

| Value item | Goes to | Why they value it |
|---|---|---|
| **A referral with its evidence** — the indicators and why they corroborate | SIU | a referral worth opening; a bad one costs the unit an hour it does not have |
| **Avoided indemnity** — claims not paid that should not be | The premium pool | **honest policyholders do not fund fraud** — this is the real customer of VS2 |
| | Insurer | loss ratio |
| **An investigation disposition** — return to VS1, or close | Claims operation | the claim can move again |
| | Policyholder | being investigated and then cleared is better than silence |
| **Evidence package** | Legal | the basis for denial or prosecution |
| **Fraud pattern intelligence** | Underwriting | what to price for |
| | SIU | what to look for next |
| | ⚠ **not produced today** | dispositions are not fed back anywhere |
| **Regulatory anti-fraud reporting** | Regulator | many jurisdictions mandate an SIU function and referral reporting |

The customer of VS2 is **not the claimant** — it is every other policyholder.
That is worth being explicit about, because it is the one stream whose value
is invisible to the person whose claim is being worked.

### VS3 — Recovery (Subrogation)

| Value item | Goes to | Why they value it |
|---|---|---|
| **An identified recoverable** — this loss was someone else's fault | Subrogation | the work cannot start without it |
| | ⚠ **not produced today** | the evidence to spot one is assembled in W3 and then discarded |
| **A recovery demand** against the at-fault carrier | The other carrier | a claim they must handle |
| **Recovered funds** | Insurer / premium pool | money back, which holds premiums down |
| **Deductible reimbursement** | **Policyholder** | when subrogation recovers, the insured's deductible is returned pro rata |

That last row is the one people forget. **VS3 has a value item that goes to
the customer**, and it is money they already paid. Quietly abandoning
subrogation does not only cost the insurer — it costs the policyholder their
deductible back.

---

## Two different stakeholder lists, and why

[`STAKEHOLDERS.md`](STAKEHOLDERS.md) and the table below share **no names at
all**, which looks like an error and is not. They are different populations:

| | Who | Example |
|---|---|---|
| **Engagement stakeholders** — `STAKEHOLDERS.md` | people who fund, approve, review or block **the project** | the CISO can stop rollout and receives nothing from any value stream |
| **Value stakeholders** — below | whoever **receives the output** of the work | the policyholder receives almost everything and sits in no meeting |

The overlap is thin on purpose. The policyholder and the regulator are the two
most consequential value stakeholders and **neither has a seat in the
engagement** — nobody in the project room speaks for them, which is exactly
why the success criteria have to.

## Stakeholders, across all three streams

| Stakeholder | Receives from | Cares most about |
|---|---|---|
| **Policyholder / claimant** | VS1, VS3 | indemnity, an explanation, speed, their deductible back |
| **Adjuster** | VS1 | a decision they can defend; not wasting a read on a claim they cannot finish |
| **SIU** | VS2 | referrals worth opening |
| **Compliance** | VS1, VS2 | a defensible trail, inside the statutory clock |
| **Finance** | VS1, VS3 | reserve accuracy and recovered funds |
| **Underwriting** | VS1, VS2 | loss statistics and fraud patterns to price against |
| **The premium pool** (every other policyholder) | VS2, VS3 | not funding fraud; not funding other people's negligence |
| **Regulator** | VS1, VS2 | deadlines met, decisions defensible, anti-fraud function exists |

---

## What this tells the engagement

Three of the value items above are **not produced at all today**, and they are
the three the success criteria were already pointing at:

| Missing item | Stakeholder going without | Success criterion |
|---|---|---|
| A rationale naming the governing clause | Compliance, the policyholder | decision accuracy; citation enforcement |
| Routing foreknowledge | the adjuster | pipeline latency; the 44% figure |
| A referral carrying its evidence | SIU | fraud routing accuracy |

ClaimSense produces all three. That is a more precise statement of what the
pilot is for than "faster claims" — and it names the stakeholder who is
currently going without each one.

The two it does **not** address — reserve accuracy and subrogation
identification — are named in the opportunities section below rather than
quietly omitted.

---

## VS1 — Claim Settlement

### The six stages

A stage boundary is where the **state of the claim changes** — where it
becomes a different kind of thing. That is what separates a stage from a
step: finishing W2 means the claim now *has a known coverage position*, and
no amount of further evidence-gathering changes that fact.

| Stage | The claim becomes… | Workflows | Owned by |
|---|---|---|---|
| **1 · Capture** | *reported* — a loss is now a claim with a number | W1 | intake |
| **2 · Establish** | *covered or not* — the policy position is known | W2 | adjuster |
| **3 · Assess** | *quantified* — what happened and what it is worth | W3 · W4 · W4a | adjuster, appraiser |
| **4 · Decide** | *decided* — an outcome exists and is authorised | W5 · W6 | adjuster ladder |
| **5 · Deliver** | *settled* — the claimant has been told, and paid | W7 · W8 | adjuster, finance |
| **6 · Close** | *closed* — the reserve is released and the record is final | W9 | adjuster |

Two things the stage view makes visible that the workflow list does not:

**Stage 2 is cheap and decisive, and it runs late.** Establishing cover is
minutes of work against PAS, and it can end the claim outright: **9 of the 62
claims in the queue have no cover in force** — lapsed before the loss (4403),
dated before inception (4410), or pointing at a policy PAS does not resolve
(4412).

Today stage 2 happens *after* an adjuster has opened the file and begun
reading. **Roughly one claim in seven has stage-3 evidence work done on it
before anyone discovers there was never any cover.**

**Stage 4 is where the desk changes.** Authorisation and total-loss routing
both land here, which is why 44% of claims stall at a boundary that is pure
arithmetic.

### The workflow chain

```
W1 Intake   →  W2 Coverage  →  W3 Evidence  →  W4 Valuation
                                                    ↓
  W9 Close ← W8 Pay ← W7 Communicate ←  W6 Authorise  ←  W5 Adjudicate
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
| **W8** | Pay — execute the settlement *(out of pilot scope)* | | C | | **A** | | | I |
| **W9** | Close — release the reserve, finalise the record *(out of pilot scope)* | | **R/A** | | I | | | C |

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
| W8 Pay | CMS + finance | minutes | **batch cycle** | payment runs, not claims |
| W9 Close | CMS | minutes | **often never** | closure is nobody's priority once the money is out |

> **NEEDS OWNER** — the process and lead times above are shape, not
> measurement. Real figures come from a time study with the Lead Adjuster in
> week 1, and the four success criteria are calibrated against that baseline.
> They are deliberately left as descriptions rather than invented numbers.

### What the data already shows

Measured against the seeded queue, not estimated:

| | | Means |
|---|---|---|
| **62** claims | in the queue | — |
| **20** | past the 15-day acknowledgement deadline | **32%** of the book is already late to acknowledge, and one claim has breached the 40-day decision deadline |
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

### The three stages

| Stage | The claim becomes… | Workflows |
|---|---|---|
| **1 · Flag** | *suspected* — indicators exist and cross a threshold | F1 · F2 |
| **2 · Investigate** | *examined* — someone has actually looked | F3 |
| **3 · Dispose** | *cleared or denied* — it rejoins VS1, or it ends here | F4 |

Short enough that a stage is close to a workflow, and saying so is more honest
than inventing a layer. The boundary that matters is **1 → 2**: before it the
claim is still in VS1 and merely flagged; after it, VS1 has stopped.

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

### The three stages

| Stage | The recovery becomes… | Workflows |
|---|---|---|
| **1 · Identify** | *recognised* — someone else was at fault | S1 |
| **2 · Pursue** | *demanded* — a claim exists against their carrier | S2 |
| **3 · Resolve** | *recovered or abandoned* | S3 |

Stage 1 is the one that fails. The evidence to recognise a recoverable claim
is assembled in **VS1 stage 3** and then discarded at VS1 stage 6 — so VS3
starts from nothing, on a claim that is already closed.

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
stage 1   W1 Intake      ░░░░  human — the claimant talks to a person
stage 2   W2 Coverage    ████  AUTOMATED — and it now runs FIRST
stage 3   W3 Evidence    ████  AUTOMATED
          W4 Valuation   ████  AUTOMATED
          W4a Total loss ▒▒▒▒  ROUTED to an appraiser, not performed
stage 4   W5 Adjudicate  ████  AUTOMATED — produces a recommendation
          W6 Authorise   ▒▒▒▒  ROUTED — the ladder is computed, the signature is human
stage 5   W7 Communicate ▓▓▓▓  DRAFTED — a licensed adjuster confirms before it is sent
          W8 Pay         ░░░░  out of scope
stage 6   W9 Close       ░░░░  out of scope
```

| | What ClaimSense does |
|---|---|
| **W2 · W3 · W4** | performed end to end — reads all three systems, establishes cover, assembles the file, computes what is payable |
| **W5** | performed — reaches one of four outcomes with the governing clause cited |
| **W4a · W6** | **computed, not performed** — which desk the claim needs is arithmetic, and ClaimSense works it out *before* anyone opens the file |
| **W7** | drafted only — nothing reaches a claimant unconfirmed |
| **W1 · W8 · W9** | untouched |
| **F3 · F4 · VS3** | untouched |

### In stage terms

| Stage | ClaimSense |
|---|---|
| 1 · Capture | **untouched** — a person in distress talks to a person |
| 2 · Establish | **performed**, and critically it now runs *first* |
| 3 · Assess | **performed** — all three systems, the clause, the arithmetic |
| 4 · Decide | **drafted and routed** — the outcome is proposed, the desk is computed, the signature is human |
| 5 · Deliver | **drafted only** — nothing is sent or paid unconfirmed |
| 6 · Close | **untouched** |

The pilot occupies **stages 2 to 4**. It does not shorten any stage so much as
**reorder** them: stage 2 and the stage-4 routing both move to the front,
before a human opens the file.

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
