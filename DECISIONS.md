# Architectural decisions

One entry per decision that would be expensive to reverse, with the reason and
what was given up. Dates are when the decision was made.

> **A note on authorship.** The engagement's judgment artifacts — the charter,
> the SoW, the risk register and the commercial calls — are the engineer's to
> write, not an assistant's. The entries below record decisions that are
> *visible in the code* and were settled by building: anywhere a decision rests
> on client context rather than on what the system does, it is marked
> **NEEDS OWNER** rather than invented.

---

## ADR-0001 — Three schemas, no cross-schema foreign keys
**2026-10-22 · accepted**

CMS, PAS and DMS live in separate Postgres schemas, and `cms.claims.policy_id`
carries **no** foreign key to `pas.policies`.

In the engagement these are three vendors' databases. There is no referential
integrity across them in the real estate, and granting it here would make the
integration work look easier than it is — the pipeline would be written against
a guarantee that evaporates on day one. Claim 4412 deliberately points at a
policy PAS has never heard of, so the dangling reference is exercised rather
than assumed away.

**Given up:** the database cannot catch a bad reference. The pipeline has to,
and `eligibility.check(policy=None)` is where.

---

## ADR-0002 — Money is integer cents, everywhere
**2026-10-22 · accepted**

`BIGINT` in the schema, `int` in Python, `z.number().int()` on the wire. No
`NUMERIC`, no float, one formatting function.

A settlement is the number a claimant receives. Floats make it a cent out
occasionally and unpredictably, and a book of claims cannot then be reconciled.
`tests/test_boundary.py` fails the build on a float literal or a true division
in `money.py`.

This caught a real bug: `pg` returns `BIGINT` as a *string*, so
`claimed_amount_cents` arrived as `"2900000"` — failing the contract and making
`a + b` string concatenation anywhere validation was bypassed.

**Given up:** amounts above 2^53 cents (~$90tn) would need revisiting. The
int8 parser throws rather than silently truncating.

---

## ADR-0003 — The deterministic/model boundary is enforced, not documented
**2026-10-22 · accepted**

Identity, access control, dates and money live in `determinism/`, which may not
import an agent SDK, `litellm` or `boto3`. A test walks the AST and fails the
build.

A boundary that exists only in a diagram erodes: someone reaches for a model to
settle an awkward date, the diagram still shows the box, and the control the
client was sold is quietly gone. The test is what makes the architecture a
property of the build rather than of the documentation.

**Given up:** some duplication. `determinism/identity.py` and
`lib/api/scope.js` state the same rules in two languages, because the console
and the agent are different trust boundaries and a control enforced on one path
only is not a control.

---

## ADR-0004 — Mock is the CI brain, not a stand-in for it
**2026-10-22 · accepted**

`--mock` is the default, runs on the stdlib alone, and is what every gate is
measured on. The live Agents SDK path is never required to pass a milestone.

A gate that can fail because a wheel would not build, a quota ran out or wifi
dropped is a gate nobody trusts. Determinism matters as much: the same claim
must produce the same answer every run, or an eval that passes today fails
tomorrow for reasons nobody changed.

**Given up:** the mock reasoner is phrase matching and will miss a paraphrase
it was not given. That fragility is real and is exactly what the live path
removes. `tests/test_backend_parity.py` stops the two drifting.

---

## ADR-0005 — BM25 over the clause corpus, not embeddings
**2026-10-22 · accepted**

Lexical retrieval, local, 46 clauses, implemented in ~20 lines rather than
pulled from a library.

Three reasons in order of weight: the gate must run with no key and no network;
the same claim must retrieve the same clauses every time; and the query is a
peril plus controlled legal vocabulary over a small corpus — where lexical
matching is strongest and semantic search buys least.

**Given up:** vocabulary mismatch. Measured, and worse than expected: the
wear-and-tear exclusion scored *last of 25* on a claim saying the roof "has
been leaking". Mitigated by a `keywords` field carrying claimant vocabulary,
by pinned grants, and by the peril pre-filter. A paraphrase none of those
anticipate is still missed — the citation tripwire turns that into a human
review rather than a wrong answer.

**Revisit when** the corpus outgrows a few hundred clauses, or a second
product line arrives with its own vocabulary.

---

## ADR-0006 — Typed contracts mean runtime-validated, not TypeScript
**2026-10-22 · accepted**

The console is JavaScript and JSX. The contracts are Zod schemas that validate
every real request and generate the OpenAPI in `docs/openapi/`.

A TS interface describes what a well-behaved caller sends; a Zod schema is what
happens when one does not. For an integration boundary the second is the
stronger guarantee, and it lets the contract carry rules a type cannot: a
settlement on a `DENY` is refused, and a model-sourced `APPROVE` with no
citation is refused — at the API, not only in the agent.

**Given up:** no compile-time checking inside the app. Mitigated by the schemas
being the single source of truth for both validation and the published spec, so
the document cannot drift from the enforcement.

---

## ADR-0007 — Three credentials, one per client system
**2026-10-22 · accepted**

`csk_cms_…`, `csk_pas_…`, `csk_dms_…`. A key for one system is refused by the
others with **403 `wrong_system`**, not 401.

Three vendors, three contracts, three credentials: a compromise of one must not
hand over the other two. 403 rather than 401 because the caller authenticated
fine — they are at the wrong door — and the primary caller is an agent, which
recovers from "use the PAS key" and loops forever on "unauthorized".

---

## ADR-0008 — The agent holds no licence
**2026-10-22 · accepted**

ClaimSense acts as adjuster seat 5: `scope='all'`, `license_number NULL`.

It must read every claim to work a queue, and must never confirm its own
recommendation. Rather than a special case, it is denied by the *same* check
that denies the SIU analyst — confirming requires a licence, and it has none.
Nothing in the code says "the agent may not confirm", which means there is no
flag to flip by accident.

---

## ADR-0009 — Quarantine drops; the FNOL is fenced instead
**2026-10-22 · accepted**

A poisoned document is dropped whole, never sanitised. The claimant's first
notice of loss cannot be dropped — it is evidence — so an injection there is
wrapped in an untrusted-content marker and the citation tripwire is what makes
a successful injection harmless.

Stripping an injected sentence assumes the sanitiser caught every variant, and
an attacker needs only the one it missed.

**Given up:** quarantine has a cost and the system pays it. On claim 4409 the
poisoned file is the only estimate, so the outcome is `MORE_INFO` rather than
`APPROVE`. That is the correct trade: an attacker cannot complete a claim file
by submitting a hostile document.

---

## ADR-0010 — The seed is idempotent by guard
**2026-10-22 · accepted**

`schema.sql` opens with `DROP SCHEMA … CASCADE`. The compose `seed` service
checks whether data exists and exits early unless `FORCE_SEED=1`.

Compose re-runs a dependency for anything depending on it, so
`docker compose run agent` was silently re-seeding and taking the minted API
keys with it — the agent then failed 401 against a stack that was plainly
healthy.

---

## ADR-0011 — The gate's authority is its exit code
**2026-10-22 · accepted**

`build-and-push` declares `needs: [test, eval, integration]`. The eval CLI
exits non-zero on a rate failure, a missing outcome, or any `ADV-*` regression.

This exists as an ADR because it was briefly *not* true. `__main__.py` called
`main()` without `sys.exit()`, so the gate printed `GATE FAILED` in red and
exited 0 — CI would have gone green and pushed the image. Every visible signal
said the gate worked; only `$?` disagreed, and `$?` is the only thing CI reads.
`tests/test_gate_exit_code.py` runs the CLI as a subprocess for that reason.

---

## Open — NEEDS OWNER

These depend on client context rather than on the system, and are flagged
rather than invented.

| # | Question | Why it matters |
|---|---|---|
| 1 | Are `APPROVE / DENY / MORE_INFO / SIU_REFERRAL` the client's actual four outcomes? | The brief says "four" and never names them. Everything downstream — the schema enum, the eval suite, the badges — assumes this set. |
| 2 | What are the real per-state fair-claims deadlines? | `clock.py` uses 15/40 days with an empty `STATE_OVERRIDES`. Inventing fifty states' statutory deadlines would be fabrication dressed as thoroughness. |
| 3 | Who owns the SIU referral threshold? | Currently 70, a constant. It is a business policy decision with a false-positive cost attached. |
| 4 | What confidence floor should force human review regardless of outcome? | There is none today. Precedence is structural, not confidence-weighted. |
| 5 | Retention and deletion for `platform.audit_log` and `agent_runs`? | Both grow without bound. |
