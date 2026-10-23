# ClaimSense

A claims-adjudication co-pilot. It reads a claim across the three systems an
adjuster works by hand — the **claims management system**, the **policy
administration system**, and the **document store** — checks coverage against the
policy corpus, assesses fraud risk, and drafts a first decision.

**A licensed adjuster confirms every outcome.** ClaimSense recommends; it never
decides. Nothing is written back until a human says so.

```bash
make up      # 1. Postgres + the three system schemas + synthetic seed + scoped keys
make web     # 2. the adjuster console on http://localhost:3200
make agent   # 3. the pipeline works one claim and writes a recommendation
```

None of that needs an API key, a cloud account, or the internet.

## The four outcomes

| Outcome | When |
|---|---|
| `APPROVE` | coverage confirmed, policy in force, within limits, no fraud signal |
| `DENY` | excluded peril, policy lapsed, or outside limits |
| `MORE_INFO` | evidence insufficient — the specific missing documents are named |
| `SIU_REFERRAL` | fraud indicators over threshold → Special Investigations Unit |

## What is code and what is judgment

The split is enforced, not described. Deterministic operations never reach a
model, and model judgment never computes money.

| Deterministic — `agent/src/claimsense_agent/determinism/` | Model judgment — `agent/src/claimsense_agent/agents/` |
|---|---|
| identity, access control, role scope | reading the file: FNOL narrative, notes, documents |
| policy dates: in-force, lapse, waiting period | coverage interpretation — **must cite retrieved clause ids** |
| money: deductible, limits, coinsurance (integer cents) | risk and fraud-indicator interpretation |
| the fraud-score threshold arithmetic | the drafted decision and its rationale |

Every judgment states the evidence it relied on. A verdict the model produced is
stamped `source: "model"`; one a deterministic check overrode is stamped
`source: "deterministic_fallback"` — they are never the same kind of output.

## Synthetic data only

No production or personally identifiable data at any stage. The seed is
generated from a fixed seed, so every run of `make up` produces the same claims.

## Layout

```
agent/      the pipeline: four agents, the determinism modules, retrieval, guardrails
platform/
  db/       schema for the three systems + the synthetic seed generator
  web/      the adjuster console and the three system APIs (Next.js, JS + JSX)
docs/       charter, SoW, architecture, contracts, risk register
  brief/    the client brief this engagement started from
```

## Commands

| Target | What it does |
|---|---|
| `make up` | Postgres, the three schemas, the synthetic seed, two scoped keys |
| `make web` | the console on `:3200` |
| `make agent` | runs one claim end to end with a traced scorecard |
| `make verify` | the $0 gate: prerequisites + smoke eval + unit tests |
| `make eval` | the eval gate CI runs on every PR |
| `make golden` | the full suite including the adversarial cases |
| `make down` | stop Postgres (`make clean` also drops the volume) |
