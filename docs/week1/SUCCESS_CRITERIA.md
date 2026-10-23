# Success criteria — Northwind Mutual pilot

Four criteria, each with a metric, a threshold, and the population it is
measured over. These become the acceptance criteria of the statement of work
verbatim.

Each is written so it can be **failed**. A criterion that cannot fail is a
slogan.

---

## 1. Decision accuracy

| | |
|---|---|
| **Metric** | Outcomes matching the licensed adjuster's independent decision |
| **Threshold** | **≥ 92%** agreement, **and ≥ 97%** on claims where cover was not in force |
| **Population** | The 150-claim golden set, blind-reviewed by the Lead Adjuster |
| **Measured by** | `claimsense-agent eval --suite golden` against adjuster-labelled outcomes |

**Why two numbers.** Coverage interpretation is genuinely contestable and 92%
reflects that two adjusters do not always agree either. Whether a policy was
in force on a date is not contestable — it is arithmetic, and a system that
gets it wrong 3% of the time is not shippable. The second threshold is on the
deterministic path and is deliberately close to perfect.

**Baseline.** Adjuster-to-adjuster agreement on the same claims, measured
during week 1. Without it, 92% is a number with nothing behind it.

---

## 2. Pipeline latency

| | |
|---|---|
| **Metric** | Wall-clock from claim assignment to a recommendation available |
| **Threshold** | **p50 ≤ 60s, p95 ≤ 180s** |
| **Population** | All claims worked in the pilot window |
| **Measured by** | `platform.agent_runs.duration_ms` |

**Why p95 and not an average.** An average hides the long tail, and the long
tail is where an adjuster gives up and opens the three tabs instead. The
number that matters is the slow case, not the typical one.

**What this is not.** Not a claim cycle-time target. Cycle time depends on
documents arriving and claimants responding, neither of which automation
touches. Measuring it here would claim credit for something the pilot does not
control.

---

## 3. Adjuster confirmation rate

| | |
|---|---|
| **Metric** | Recommendations confirmed without override |
| **Threshold** | **≥ 80%** by week 4, with **100% of overrides carrying a reason** |
| **Population** | All recommendations reaching an adjuster |
| **Measured by** | `cms.decisions.override_outcome IS NULL` over confirmed rows |

**Why this is the adoption metric, not an accuracy one.** A system that is
right but not trusted gets overridden anyway, and the override rate is the
only honest signal of whether adjusters are using it or routing around it.

**The second half matters more than the first.** Every override with a reason
becomes an evaluation case. A high override rate with good reasons is a
system that is improving; a low one with empty reasons is a rubber stamp,
which is worse than a high one.

---

## 4. Fraud routing accuracy

| | |
|---|---|
| **Metric** | Referrals the SIU opens an investigation on, and referrals missed |
| **Threshold** | **≥ 70% precision** on referrals, **≤ 5% miss rate** on claims SIU later opens independently |
| **Population** | All claims scored during the pilot, reconciled with SIU at the end |
| **Measured by** | `cms.decisions.outcome = 'SIU_REFERRAL'` against SIU's own disposition |

**Why precision is only 70%.** Referral is an *invitation to look*, not an
accusation. A false positive costs the unit an hour; a false negative costs a
paid fraudulent claim. The asymmetry is deliberate and the SIU Manager agreed
it in discovery.

**Why the miss rate is the harder number.** It is measured against claims SIU
found by other means — which means it can only be computed after the fact, and
it is the one criterion that cannot be gamed by tuning the threshold upward.

---

## What is deliberately not a criterion

**Cost per claim.** Real, and tracked, but it is a vendor concern. Making it
an acceptance criterion would invite trading decision quality for token spend.

**Full automation rate.** There is none, by design. Every outcome is confirmed
by a licensed adjuster, and a criterion that rewarded removing that would be
rewarding the wrong thing.

---

## How they are reported

| Criterion | Cadence | To |
|---|---|---|
| Decision accuracy | per golden run, gated in CI | Lead Adjuster, VP Claims |
| Pipeline latency | continuous | us; escalated on p95 breach |
| Confirmation rate | weekly | Lead Adjuster, VP Claims |
| Fraud routing | end of pilot, reconciled | SIU Manager, VP Claims |

**NEEDS OWNER** — the thresholds above are proposed from discovery. Each needs
the named accountable stakeholder to accept it before it enters the SoW.
