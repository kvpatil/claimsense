# Week 4 architecture — M4, integrated into Claims Desk

**Milestone.** *M4 — integrated into Claims Desk.* Gate: **the two-adjuster
confirmation test passes.** Sign-off: Lead Adjuster **and** IT. See
[`../week2/SOW.md`](../week2/SOW.md) §4.

Week 3 delivered the capability standalone. Week 4 puts a recommendation in a
licensed adjuster's hands and lets her act on it — which means three new flows,
a governed door for tool access, and identity at the integration boundary.

**Week 4 adds flows 12–14, MCP, and RBAC at the boundary.**

---

## What changes

```
                    ┌──────── Week 3 pipeline, unchanged ────────┐
                    │  flows 1-11 · guardrails · scorecard       │
                    └────────────────────┬───────────────────────┘
                                      12 │ POST /claims/{id}/decisions
                                         │ Idempotency-Key, audited
                    ┌────────────────────┴───────────────────────┐
                    │ CMS — cms.decisions                        │
                    │ the row lands with confirmed_by = NULL     │
                    │ it is NOT a decision until a human says so │
                    └────────────────────┬───────────────────────┘
                                      13 │ recommendation + evidence
                    ┌────────────────────┴───────────────────────┐
                    │ CLAIMS DESK — Northwind's own portal       │
                    │ cited clauses in full · retrieved vs cited │
                    │ model verdict and deterministic_fallback   │
                    │ wear different badges                      │
                    └────────────────────┬───────────────────────┘
                                      14 │ confirm or override
                    ┌────────────────────┴───────────────────────┐
                    │ LICENSED ADJUSTER                          │
                    │ license_number IS NULL → REFUSED           │
                    │ the agent's own seat has none              │
                    │ every override carries a reason            │
                    └────────────────────────────────────────────┘

  NEW, cross-cutting:
    ⌸ MCP          the governed door for tool access
    ⚿ RBAC/OAuth2  on-behalf-of, scoped per seat, at the boundary
```

---

## Flows

| # | Flow | Carries | Guarded by | State |
|---|---|---|---|---|
| 1–11 | the Week 3 pipeline | — | — | ✅ done |
| 12 | Pipeline → CMS | the recommendation | `Idempotency-Key`, audit | **built, gated** |
| 13 | CMS → console | `confirmed_by IS NULL` | — | **built, gated** |
| 14 | Adjuster → CMS | confirm or override | **licence required** | **built, gated** |
| — | Agent ↔ tools via MCP | tool calls | the governed door | ✗ to build |
| — | Caller → integration layer | identity per seat | OAuth2 on-behalf-of, RBAC | ✗ to build |

### Already built and deliberately gated

`--write` and the portal's confirm control exist and are tested, held behind
`CLAIMSENSE_STAGE` (default `week3`):

```bash
… run --claim 4414 --live --write          # refused, naming the variable
CLAIMSENSE_STAGE=week4 … --write           # the Week 4 path
```

At `week3` the portal shows a recommendation with a **labelled placeholder**
where the confirm control will be — an absent control reads as a missing
feature; a labelled one reads as a scope boundary.

Write-back mechanics are in
[`../../agent/src/claimsense_agent/writeback.py`](../../agent/src/claimsense_agent/writeback.py):
`idempotency_key` fingerprints the body, `write_back` posts the
recommendation, `record_run` writes telemetry to `platform.agent_runs`.

### Still to build

| | Why it is Week 4 and not earlier |
|---|---|
| **MCP** | the governed door for tool access. Today the agent calls Python functions directly; MCP makes tool access a boundary that can be audited and policed rather than a function call |
| **OAuth2 on-behalf-of + RBAC at the boundary** | Week 3's RBAC is `determinism/identity.py` — *the agent* deciding who may view and who may confirm. Week 4's is the *integration layer* authenticating a real seat. **These two must compose, not duplicate.** Settle this before writing either |
| **The two-adjuster confirmation test** | M4's gate. Two different licensed seats, two claims, confirm and override, and the audit log proving who owned each outcome |

---

## Idempotency is correctness here, not convenience

A duplicated claim decision is a duplicated payment.

| Replay | Result |
|---|---|
| same key, same body | the original record, `Idempotent-Replay: true` |
| same key, **different** body | **409** |
| already confirmed | **409**, never a silent overwrite of who owned the outcome |

Returning the first response on a changed body would silently discard the
second intent — an adjuster who confirmed `APPROVE`, changed to `DENY` and
reused the key would be told the denial succeeded while the approval stood.

---

## The gate

**The two-adjuster confirmation test.** Not a pass rate — a demonstration that
two licensed adjusters can each confirm or override a recommendation, that the
unlicensed agent seat cannot, and that the audit log attributes every outcome.
IT signs alongside the Lead Adjuster because this is the first milestone that
writes to a client system.

## Status

Flows 12–14 built and tested behind the stage gate. MCP, boundary RBAC and the
acceptance test remain. **No Week 4 brief exists in the repo** — this scope
comes from the SoW timeline and
[`../week3/README.md`](../week3/README.md) *Not in Week 3 scope*.
