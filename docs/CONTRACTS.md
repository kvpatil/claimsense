# Typed contracts — CMS · PAS · DMS

Three client systems, three contracts, three credentials. A key scoped to one
is refused by the others with **403 `wrong_system`** — the caller
authenticated, they are simply at the wrong door.

**"Typed" means validated at runtime.** The console is JavaScript, so there are
no TypeScript interfaces; instead every request passes a Zod schema on a real
request. Those same schemas generate `docs/openapi/{cms,pas,dms}.json`, so this
document and the enforcement are the same artifact and cannot drift apart.

Source of truth: `platform/web/src/lib/contracts/`.
Regenerate the specs with `cd platform/web && npm run contracts`.

---

## Shared vocabulary

| Type | Shape | Note |
|---|---|---|
| `Cents` | `z.number().int()` | **Money is always integer cents.** A JSON number is a float64, so sending dollars invites `1234.56` arriving as `1234.5600000000001`. `.int()` rejects a decimal at the boundary. |
| `Outcome` | `APPROVE \| DENY \| MORE_INFO \| SIU_REFERRAL` | matches `cms.decisions.outcome` |
| `VerdictSource` | `model \| deterministic_fallback` | matches `cms.decisions.source` |
| `IsoDate` / `IsoDateTime` | `YYYY-MM-DD` / RFC3339 with offset | |

### Error envelope

```json
{ "error": { "code": "wrong_system",
             "message": "This key is scoped to the CMS contract…",
             "hint": "Use PAS_API_KEY for this endpoint." } }
```

`hint` is not decoration. The primary caller is an agent, and one told *how to
recover* retries correctly instead of looping or escalating.

| Status | Means |
|---|---|
| 401 | no key, or an unrecognised/revoked one |
| 403 | valid key, wrong system — or this seat may not touch this resource |
| 404 | the resource does not exist (**contractual** for PAS policies) |
| 409 | `Idempotency-Key` reused with a different body |
| 422 | body failed contract validation |

---

## Idempotency — required on every write

A duplicated claim decision is a duplicated payment. This is correctness, not
convenience.

| Situation | Result |
|---|---|
| fresh key | proceed, then record |
| same key, **same** body | the **original** record, 200, `Idempotent-Replay: true` |
| same key, **different** body | **409** |

* **Scope:** unique per `(adjuster, system)`. Two seats may reuse a key string.
* **Fingerprint:** sha256 of the body with keys sorted, so a re-ordered but
  identical body is recognised as a replay.
* **Why 409 and not "return the first":** that would silently discard the
  second intent. An adjuster who confirmed `APPROVE`, changed to `DENY` and
  reused the key would be told their denial succeeded while the approval stood.

The agent derives its key from the trace id —
`claimsense-{claim_id}-{trace_id}` — so retrying *this* run replays, while a
genuinely new reading of the same claim writes a new row.

---

## CMS — Claims Management System

Base `/api/cms/v1` · key `CMS_API_KEY` · **the only system ClaimSense writes to**

| Method | Path | Notes |
|---|---|---|
| GET | `/claims` | the queue, scoped in SQL — a seat never receives a row it may not see |
| GET | `/claims/{id}` | |
| GET | `/claims/{id}/fnol` | the claimant's own words; **attacker-influenceable** |
| GET | `/claims/{id}/notes` | |
| GET | `/claims/{id}/fraud-signals` | weights ship with the signals, so the score is reproducible |
| GET | `/claims/{id}/decisions` | |
| **POST** | `/claims/{id}/decisions` | record a recommendation · idempotent |
| **POST** | `/decisions/{id}/confirm` | **licence required** · idempotent |
| GET | `/adjusters/{id}` | |

### POST `/claims/{id}/decisions`

```json
{ "outcome": "APPROVE",
  "source": "model",
  "rationale": "The loss is covered…",
  "cited_clause_ids": ["HO3-I-A-1"],
  "settlement_cents": 1750000,
  "confidence": 0.88 }
```

Rules the contract enforces — and a type alone could not:

* `settlement_cents` **must be null** unless `outcome` is `APPROVE`
* a `model`-sourced `APPROVE` or `DENY` **must cite at least one clause**
* `source` is **required with no default** — a caller that cannot say whether a
  model or a deterministic check produced the verdict has not met the
  milestone, and a default would let it pass silently

The row lands with `confirmed_by NULL`. It is a *recommendation* until a human
confirms.

### POST `/decisions/{id}/confirm`

```json
{ "adjuster_id": 1,
  "override_outcome": "MORE_INFO",
  "override_reason": "Want the plumber report before denying." }
```

* the seat must hold a **licence** — `license_number IS NULL` → 403
* `adjuster_id` must match the seat the key acts as → else 403
* an override **must** carry a reason ≥ 10 chars. Every override is a future
  eval case, which is the most valuable data this product generates
* already confirmed → **409**, never a silent overwrite of who owned the outcome

---

## PAS — Policy Administration System

Base `/api/pas/v1` · key `PAS_API_KEY` · **read-only**

| Method | Path | Notes |
|---|---|---|
| GET | `/policies/{id}` | **404 is contractual** — see below |
| GET | `/policies/{id}/coverages` | limits, deductibles, coinsurance |
| GET | `/clauses` | the corpus retrieval ranks over |

**There is no write contract, deliberately.** An automated adjudicator that
could alter a policy could manufacture the coverage it then finds.

**On the 404.** `cms.claims.policy_id` crosses a vendor boundary with no
foreign key behind it, so a dangling reference is reachable in production — it
is not an exceptional condition. The agent treats it as *policy not
resolvable*, reports it, and returns `MORE_INFO`. It must never be a 500.
Claim 4412 is the planted case.

**`/clauses` returns the whole corpus** and ranking happens in the agent.
That keeps the $0 gate database-free, and 46 clauses is nothing to ship. It
must include `keywords` — the field carrying claimant vocabulary — because an
endpoint that omits it silently degrades the live path relative to the offline
one. That drift happened once; `tests/test_backend_parity.py` now catches it.

---

## DMS — Document Store

Base `/api/dms/v1` · key `DMS_API_KEY`

| Method | Path | Notes |
|---|---|---|
| GET | `/documents?claim_id=…` | returns poisoned documents **flagged, not filtered** |
| **POST** | `/document-requests` | ask the claimant for a document · idempotent |

**Why poisoned documents are returned.** If this endpoint quietly dropped them,
the agent could never record that it refused one — and a quarantine nobody can
see is a quarantine nobody can audit. Dropping is the guardrail's job, at the
point where it can be logged.

`POST /document-requests` is what a `MORE_INFO` outcome produces. `reason` is
required and ≥ 10 characters: the claimant is told *why*, and "additional
documentation required" is not something a person can act on. Idempotent
because a retried pipeline must not send two letters.

---

## Audit

Every request is recorded in `platform.audit_log` with the acting seat, the
system, the action, the resource and **allow or deny**.

Denials are recorded as carefully as successes — *who tried to read what and
was stopped* is the question an audit actually asks, and a log of only
successes cannot answer it.

The audit write never throws. Losing a log line is bad; turning every read into
a 500 because the log table is full is worse.

---

## Trying it

```bash
make up            # mints all three keys into keys.env
source keys.env

curl -s -H "Authorization: Bearer $CMS_API_KEY" \
  localhost:3200/api/cms/v1/claims/4409 | jq

# the wrong door — 403, not 401
curl -s -H "Authorization: Bearer $CMS_API_KEY" \
  localhost:3200/api/pas/v1/policies/7009 | jq

# idempotency: run twice, get one row and Idempotent-Replay: true
curl -si -X POST -H "Authorization: Bearer $CMS_API_KEY" \
  -H "Content-Type: application/json" -H "Idempotency-Key: demo-1" \
  -d '{"outcome":"DENY","source":"model","rationale":"Surface water is excluded.","cited_clause_ids":["HO3-I-EXCL-3"]}' \
  localhost:3200/api/cms/v1/claims/4402/decisions | head -1
```
