# Stakeholder map and RACI — Northwind Mutual

The four roles the engagement actually turns on are the **approver**, the
**reviewer of automated output**, the **daily user**, and **whoever can block
rollout**. They are named first, because an engagement that cannot name them
is an engagement that discovers them late.

> **NEEDS OWNER** — the names below are placeholders. The *roles* and what
> each one can stop are what discovery established; the people are for the
> engagement lead to fill in.

---

## The four that matter

| Role | Who | What they control | What they fear |
|---|---|---|---|
| **Approver** | VP Claims Operations | the budget, and whether the pilot becomes production | paying for something adjusters route around |
| **Reviewer of automated output** | Lead Adjuster (licensed) | whether an outcome is trustworthy | being accountable for a decision she did not reason to |
| **Daily user** | Claims Adjuster | whether it is used at all | being measured on throughput against a tool she cannot correct |
| **Can block rollout** | CISO | production data access, the security review | an automated system reading policyholder data before it is assessed |

**The CISO is the critical path and does not report to the approver.** The VP
can fund the pilot and still not get production access. This is why the build
is synthetic-only from day one rather than as a fallback.

## Everyone else

| Role | Who | Interest |
|---|---|---|
| SIU Manager | Special Investigations | referral quality — false referrals waste the unit's time |
| Compliance Officer | Regulatory | fair-claims deadlines, decision defensibility, audit trail |
| IT Integration Lead | Platform | the three system contracts, credentials, non-production environments |
| General Counsel | Legal | who is liable for an automated decision, and what the claimant is told |
| Vendor team | Us | delivery |

---

## RACI

**R** responsible · **A** accountable · **C** consulted · **I** informed

| Deliverable | VP Claims | Lead Adj. | Adjuster | CISO | Compliance | IT | Us |
|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| Engagement charter | **A** | C | I | C | C | I | **R** |
| Success criteria | **A** | C | C | I | C | I | **R** |
| Statement of work | **A** | I | I | C | C | C | **R** |
| Security review | I | I | I | **A** | C | C | **R** |
| System access (non-prod) | C | I | I | **A** | I | **R** | C |
| Architecture | C | I | I | **A** | C | C | **R** |
| The automated workflow | I | C | C | I | I | C | **R/A** |
| Evaluation set | C | **A** | C | I | C | I | **R** |
| Decision quality sign-off | C | **R/A** | C | I | C | I | C |
| Fair-claims compliance | C | C | I | I | **A** | I | **R** |
| Production rollout | **A** | C | C | **A** | C | **R** | C |

### Two rows worth reading twice

**Decision quality sign-off** is the Lead Adjuster's, not ours. We can show a
pass rate; only a licensed adjuster can say the outcomes are right. If she
will not sign, the pilot does not proceed however green the gate is.

**Production rollout has two accountable parties.** The VP owns the business
decision and the CISO owns the data decision, and either can stop it alone.
Treating this as one approval is how a pilot gets funded, built, and then
parked.

---

## What each one needs to see

| Stakeholder | Will believe |
|---|---|
| VP Claims | throughput and consistency, measured against the current baseline |
| Lead Adjuster | the clause each decision rests on, and an easy way to overrule it |
| Adjuster | that overriding is one click and her reason is recorded, not argued with |
| CISO | synthetic-only, scoped credentials, an audit row per request including denials |
| Compliance | the decision trail, and that no outcome reaches a claimant unconfirmed |
| SIU | referrals that are worth opening |

## Engagement cadence

| When | What | Who |
|---|---|---|
| Weekly | outcome review — sample claims, every override discussed | Lead Adjuster, us |
| Fortnightly | progress against the four criteria | VP Claims, us |
| Milestone | security posture | CISO, Compliance, us |
| Ad hoc | integration unblocking | IT Lead, us |

The weekly outcome review is the one that cannot slip. Every override an
adjuster records becomes an evaluation case, and that loop is how the system
improves — it is a delivery mechanism, not a status meeting.
