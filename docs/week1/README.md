# Week 1 — Customer discovery and scoping

**Submission bundle.** What discovery established about Northwind Mutual's
existing claims workflow, and what the engagement commits to changing.

---

## Deliverables

| # | Deliverable | Where |
|---|---|---|
| 1 | Engagement charter, naming the three client systems and their integration points | [`CHARTER.md`](CHARTER.md) |
| 2 | Stakeholder map and RACI — approver, reviewer of automated output, daily user, and who can block rollout | [`STAKEHOLDERS.md`](STAKEHOLDERS.md) |
| 3 | Four quantified success criteria | [`SUCCESS_CRITERIA.md`](SUCCESS_CRITERIA.md) |
| 4 | Architectural decisions, dated, with reasons | [`../../DECISIONS.md`](../../DECISIONS.md) |
| 5 | Initial 20 evaluation cases, all four outcomes, including adversarial | [`EVAL_CASES.md`](EVAL_CASES.md) |
| 6 | Value streams, workflows, and which role is in each | [`VALUE_STREAMS.md`](VALUE_STREAMS.md) |
| — | Every acronym, expanded | [`../GLOSSARY.md`](../GLOSSARY.md) |

## See the existing system

```bash
./week1_demo.sh
```

Brings up Northwind's estate and walks the current manual workflow: the
backlog, the three systems a single claim is assembled from, and the two steps
that have no system behind them at all.

The portal is at <http://localhost:3200> — **Northwind Mutual, Claims Desk**.
There is no automation in it. Open claim 4414 and the decision panel is a
blank form: outcome, clause identifiers typed from memory, the payable amount
worked out on paper.

### What the demo makes concrete

| | |
|---|---|
| **Three systems** | a claim is assembled from CMS, PAS and DMS, by hand |
| **Two unsupported steps** | finding the governing clause, and computing what is payable — no system does either |
| **Search that does not help** | searching the wording for "water" returns five clauses, two of which decide the claim and three of which are noise. Searching the claimant's own word, "leaking", returns **zero** — the form says "deterioration" |
| **No citation trail** | nothing records which clause a decision rested on |
| **The queue grows** | 56 of 60 claims already past 25 days |

---

## Where the automation lands

The engagement is not "automate claims". It is **steps W2–W5 of the settlement
value stream**, with W1 and the decision itself left human — see
[`VALUE_STREAMS.md`](VALUE_STREAMS.md).

The most expensive fact that map surfaces: **44% of claims need a desk beyond
the first one** (over an adjuster's authority), and **16% need an appraiser**
(total loss). Nothing works that out today, so an adjuster does the reading
and only then discovers they cannot finish. The handoff is not the cost — the
work done before discovering the handoff is.

## The three client systems

| System | Role | Integration point |
|---|---|---|
| Claims Management (CMS) | system of record for the claim | claim, first notice of loss, notes, fraud indicators; decisions written back |
| Policy Administration (PAS) | system of record for cover | policy, dates, status, coverages, limits, the policy wording — **read-only** |
| Document Store (DMS) | the files on a claim | documents and extracted text; requests for missing documents |

Three vendors, three contracts, three credentials, and **no referential
integrity between them**. A claim can carry a policy reference PAS does not
resolve — case `4412` exists so the pilot handles it rather than assuming it
away.

---

## Regenerating the evaluation cases

`EVAL_CASES.md` is generated from the seed so it cannot drift from the data:

```bash
make seed     # regenerate the fixture, then re-run the generator in this file's header
```

---

## Still open

`DECISIONS.md` carries five items marked **NEEDS OWNER** — decisions that rest
on client context rather than on the system. The first is the most
consequential: **the brief names four decision outcomes but never says what
they are.** `APPROVE / DENY / MORE_INFO / SIU_REFERRAL` is an inference, and
it is baked into the schema, the evaluation suite and the console.

Stakeholder names throughout are placeholders. The roles are what discovery
established; the people are for the engagement lead.
