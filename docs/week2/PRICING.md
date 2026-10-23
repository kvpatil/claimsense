# Pricing model

Cost first, then the price. The price has to clear the cost.

> **NEEDS OWNER** — the blended day-rate and the final numbers are the
> engagement lead's. The *structure*, the assumptions and the arithmetic are
> below; substitute your rate and the model recomputes.

---

## 1. Estimate — the cost basis

| Milestone | Size | Day range | Risk × | Days (low / exp / high) |
|---|---|---|---|---|
| M1 — Discovery, charter, success criteria | S | 4–6 | 1.1 | 4.4 / 5.5 / 6.6 |
| M2 — SoW, architecture, contracts, synthetic data | M | 8–12 | 1.2 | 9.6 / 12.0 / 14.4 |
| M3 — Automated pipeline, guardrails, eval gate, CI | L | 15–22 | 1.3 | 19.5 / 24.1 / 28.6 |
| M4 — Portal integration, RBAC, write-back | M | 10–15 | 1.5 | 15.0 / 18.8 / 22.5 |
| M5 — Golden set, evidence pack, handover | M | 8–12 | 1.2 | 9.6 / 12.0 / 14.4 |
| | | | **Total** | **58.1 / 72.4 / 86.5** |

**Why the risk multipliers differ.** M3 is the largest block but the best
understood — it is our own code, in our own environment, with no client
dependency. M4 carries the highest multiplier at 1.5 despite being smaller,
because it is the first milestone that touches the client's estate: their
environments, their credentials, their change windows, their people. Work that
depends on someone else's calendar is not estimated the same way as work that
does not.

**Blended day-rate:** `$____` *(NEEDS OWNER)*

**Estimated cost:** low `58.1 × rate` · expected `72.4 × rate` · high `86.5 × rate`

## 2. Access-politics buffer

The top risk in the register, and the one juniors forget to price.

The CISO can block production data access and **does not report to the VP who
funds the pilot**. The security review is not on our critical path to *build* —
the whole pilot is synthetic-only by design — but it is on the critical path
to *prove value on real claims*, which is what the renewal conversation needs.

| Scenario | Delay | Cost |
|---|---|---|
| Review passes on schedule | 0 weeks | — |
| **Expected** — one round of follow-ups | 2 weeks | 10 days standing time |
| Pessimistic — full architecture review | 5 weeks | 25 days, M4/M5 slip |

**Buffer carried: 10 days at the blended rate.** Not contingency we hope not to
use — the expected case. A quoted price that assumes the security review passes
first time is a price that will be wrong.

**Mitigation that costs nothing.** Building synthetic-only from day one means a
delayed review delays *proof*, not *delivery*. Milestones M1–M3 complete
regardless. That is why the architecture was designed this way, and it is worth
saying out loud in the commercial conversation.

## 3. The three models

| Model | Bill on | Risk sits with | When to pick it |
|---|---|---|---|
| T&M with a cap | hours, ceiling-bounded | shared | scope still fuzzy |
| Fixed-price | a scoped deliverable | vendor | discovery was strong |
| Outcome-based | a business result | shared, results-linked | the result is clean and measurable |

## 4. Priced four ways

Using **expected 72.4 days + 10 days buffer = 82.4 days**.

| Model | Number | Notes |
|---|---|---|
| T&M with a cap | `82.4 × rate × 1.35`, capped at `× 1.25` of estimate | client carries overrun risk to the cap |
| Fixed-price | `82.4 × rate × 1.40` | we carry all overrun risk; the margin reflects it |
| Outcome-based | low base + per-claim component | unbounded upside, no floor — wrong for a first pilot |
| **Fixed floor + outcome** | `82.4 × rate × 1.20` floor, plus a per-claim component | **recommended** |

### The outcome component

Per claim **decided within the fair-claims window at or above the accuracy
threshold**, measured on the pilot population.

The definition matters more than the number. It pays on claims *decided* and
*accurate*, not on claims *processed*. Paying per claim processed would reward
volume over correctness, which is exactly the incentive an automated
adjudicator must not have.

## 5. Recommendation

**Fixed floor + outcome component.**

Procurement gets a ceiling they can approve. The board gets an alignment
story — we are paid more when more claims are decided correctly and on time.
And the floor protects delivery while the access politics resolve, which is
the risk that actually threatens this engagement.

For a regulated client running its first automation pilot, the floor is what
makes the outcome component acceptable rather than frightening. A pure
outcome deal invites the client to wonder what we will do to hit the number.

## 6. Margin check

```
price − cost − access buffer = margin
```

At the recommended model: `82.4 × rate × 1.20` against a cost of
`72.4 × rate` plus the 10-day buffer already inside the 82.4.

Sanity-check against revenue per engineer (~$0.6–1.0M / engineer / year). **If
the pilot cannot clear cost plus buffer plus margin, scope it smaller** — drop
M4 to a read-only surface and defer the write-back rather than discounting the
rate. A discounted rate sets the anchor for the production engagement; a
smaller scope does not.

---

## Assumptions, stated

1. One FDE plus fractional support. A second engineer would compress the
   calendar, not reduce the day count.
2. The blended rate includes delivery, not pre-sales.
3. **Model inference cost is not in the day rate.** Measured at well under $1
   per claim at pilot volume on the routed configuration — the cheap model does
   the high-volume stages and the expensive one touches a single step. It is
   tracked and reported, deliberately *not* an acceptance criterion: making it
   one would invite trading decision quality for token spend.
4. The synthetic-data constraint holds for the full pilot. If production access
   arrives early, M5 gains scope and should be re-priced.
5. No commercial lines, no litigated claims, no payment execution.
