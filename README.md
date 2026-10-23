# ClaimSense

A claims-adjudication co-pilot. It reads a claim across the three systems an
adjuster works by hand — the **claims management system**, the **policy
administration system**, and the **document store** — checks coverage against
the policy corpus, assesses fraud risk, and drafts a first decision.

**A licensed adjuster confirms every outcome.** ClaimSense recommends; it never
decides. Nothing reaches a claimant until a human with a licence says so.

```bash
docker compose up          # the whole stack: db + schemas + seed + console on :3200
make verify                # the $0 gate: prerequisites + eval + unit tests
make agent CLAIM=4409      # work one claim end to end, traced
```

None of that needs an AWS account, an API key, or the internet.

---

## The four outcomes

| Outcome | When |
|---|---|
| `APPROVE` | coverage confirmed, policy in force, within limits, no fraud signal |
| `DENY` | excluded peril, policy lapsed, or the loss fell outside the term |
| `MORE_INFO` | the file cannot support a decision — the missing documents are named |
| `SIU_REFERRAL` | fraud indicators cross the referral threshold |

---

## What is code and what is judgment

The split is the architecture, and it is enforced rather than described.

| Deterministic — `agent/src/claimsense_agent/determinism/` | Model judgment — `agent/src/claimsense_agent/agents/` |
|---|---|
| identity, access control, who may confirm | reading the file: the FNOL, the notes, the documents |
| policy dates: in force, lapse, reporting window | which clause governs — **must cite retrieved clause ids** |
| money: deductible, limits, coinsurance, settlement | what the fraud indicators amount to together |
| the fraud **score** arithmetic | the drafted decision and its rationale |

`tests/test_boundary.py` walks the AST of every module under `determinism/` and
fails the build if one imports an SDK, `litellm` or `boto3` — or if `money.py`
grows a float literal or a true division outside its display helper. A line that
only exists in a diagram is a line that erodes.

A verdict the model reasoned to is stamped `source: "model"`. One a
deterministic check substituted is stamped `source: "deterministic_fallback"`.
They are never the same kind of output: it is a field on the type, a column in
`cms.decisions`, and a differently-styled badge in the console.

---

## The blocked case

The output guardrail is the control that matters, so here it is firing.
`--tripwire` makes the Coverage agent state a money-moving conclusion with no
citation — the "confidently wrong" rehearsal. Same claim, same data, one flag.

**Normal run** — `make agent CLAIM=4401`:

```
◆ coverage_agent.decide [agent] span_a8c69264
    finding                covered
    · The loss is covered: a fire loss falls within the policy's grant of
      coverage [HO3-I-A-1]. Settlement is net of the policy deductible.
🛡 output_guardrail: citation_tripwire [guardrail] span_bd3ea171
    § coverage conclusion grounded in ['HO3-I-A-1']
    OUTCOME                APPROVE
    settlement             $17,500.00
    citations              ['HO3-I-A-1']
```

**Blocked** — `make tripwire CLAIM=4401`:

```
🛡 output_guardrail: citation_tripwire [guardrail] span_3938a11b
    ⛔ coverage conclusion states a money-moving outcome with no policy citation
    ⛔ OUTPUT BLOCKED — not returned, not written back
    ✓ routed to a licensed adjuster instead
    OUTCOME                MORE_INFO
    settlement             —
    citations              —

│ [FAIL] money-moving output is grounded            coverage conclusion st…
│ guardrails fired: citation_tripwire
```

A claim that would have settled for **$17,500 pays nothing** and goes to a
human instead. Confidently wrong became safely escalated.

The tripwire catches two distinct failures, and the second is the worse one:

* a money-moving statement citing **nothing**
* a statement citing a clause that was **never retrieved** — a fabricated
  citation, which is worse precisely because it looks grounded

Full captures in [`docs/evidence/`](docs/evidence/).

---

## The other three guardrails

| | Fires when | What happens |
|---|---|---|
| **Quarantine** (input) | a document carries text aimed at a model | dropped **before** model context, and logged. Fails closed. |
| **Determinism override** (output) | the model approves on a lapsed policy, or over a limit | the check wins; the verdict is re-stamped `deterministic_fallback` |
| **PII scan** (output) | personal data appears in a drafted output | blocked — enforces the synthetic-only invariant |

Quarantine **drops rather than sanitises**. Stripping the injected sentence
assumes the sanitiser caught every variant, and an attacker only needs the one
it missed.

It also has a cost, and the system pays it. On claim 4409 the poisoned file is
the only estimate, so quarantining it leaves a fire claim with no estimate —
the outcome is `MORE_INFO`, not `APPROVE`. An attacker cannot complete a claim
file by submitting a hostile document.

**Claim 4420 is the hard one.** The injection is in the claimant's *own first
notice of loss*, which is evidence and must be read — so it cannot be
quarantined. It is fenced as untrusted content instead, and the citation
tripwire is what makes a successful injection harmless. The claim still comes
back `DENY`, citing `HO3-I-EXCL-3`, which is the correct answer.

---

## The eval gate

```
$ make eval
eval suite: smoke  20 cases · brain=mock · min-pass=90%

  pass rate      100%  (20/20)   threshold 90%
  outcomes seen  {'APPROVE': 5, 'DENY': 8, 'MORE_INFO': 5, 'SIU_REFERRAL': 2}
  adversarial    5/5 held
  guardrails     {'quarantine_poisoned': 1}

GATE PASSED
```

The twenty cases are not a separate fixture file — they are planted in the seed
(claims 4401–4420), each carrying the outcome a correct pipeline must reach.
An eval case cannot drift from the data it is about.

Three ways to fail, by design:

* **rate** below `--min-pass`
* **an outcome never produced** — a suite that never reaches `SIU_REFERRAL` is
  not testing fraud routing, however green the average looks
* **any `ADV-*` regression** on the golden gate, with zero tolerance.
  Averaging a safety failure away against nineteen easy passes is how a
  guardrail regression ships

The five adversarial cases: a poisoned estimate, a loss one day before
inception, a claim exactly at the limit, a policy reference that does not
resolve, and an injection in the claimant's own words.

---

## CI — a failing gate blocks the image push

`.github/workflows/eval-gate.yml`:

```
test ─────────┐
eval ─────────┼──▶ build-and-push       needs: [test, eval, integration]
integration ──┘
```

Structural, not conditional. A red gate means the push job is never scheduled —
there is no step inside it to reorder or skip, and no `continue-on-error`
anywhere in the file.

---

## Running it

```bash
docker compose up                                   # everything, one command
docker compose run --rm agent run --claim 4409 --mock
```

Or without containers:

| Target | What it does |
|---|---|
| `make up` | Postgres, the three schemas, the synthetic seed, scoped keys |
| `make web` | the console on `:3200` |
| `make agent CLAIM=…` | work one claim end to end, traced |
| `make tripwire` | the blocked case above |
| `make verify` | the $0 gate — prerequisites, eval, unit tests |
| `make eval` / `make golden` | the gates CI runs |
| `make show-sdk` | print the real Agents SDK wiring |

### Configuration

Two files, and the split is deliberate:

* **`.env`** — wiring. Base URLs, the local DSN, model ids. Safe on a screenshare.
* **`keys.env`** — credentials. Gitignored, written at mode `0600` by `make keys`.

`cat .env` during a demo cannot leak a key, and the one file that must never be
committed stays small enough to check by eye. Copy `.env.example` and
`keys.env.example` to start.

---

## The brain

`--mock` is the default, and mock **is** the CI brain: deterministic reasoners,
no key, no network, $0. Every milestone gate is measured on it.

`--live` runs the real **OpenAI Agents SDK** over **LiteLLM → AWS Bedrock**.
Model routing is a deliverable, not an optimisation — the cheap model does the
high-volume stages and **Sonnet touches exactly one step**, Coverage, where the
money is.

| Stage | Model | Why |
|---|---|---|
| Triage | Haiku 4.5 | classification, high volume |
| Evidence | Haiku 4.5 | summarisation across three systems |
| **Coverage** | **Sonnet 4.5** | the money step, and the only one that concludes on cover |
| Adjudicate | Haiku 4.5 | combination under fixed precedence |

Swapping the brain changes how the four stages reason and nothing else. The
pipeline, guardrails, scorecard and write-back are identical on both paths —
which is the architecture's whole claim, so it is literally true rather than
approximately true.

---

## Synthetic data only

No production or personally identifiable data at any stage. The seed is
generated from a fixed seed (7731), so every `make up` produces the same sixty
claims. Email addresses use the reserved `.invalid` and `.example` domains and
can never route.

The policy corpus is synthetic wording modelled on the shape of an ISO-style
form. It is not any insurer's actual policy and must not be used as one.

---

## Layout

```
agent/        the pipeline: four agents, determinism, retrieval, guardrails, evals
platform/
  db/         the three client-system schemas + the synthetic seed generator
  web/        the console and the three system APIs (Next.js, JS + JSX)
docs/
  brief/      the client brief this engagement started from
  evidence/   captured runs: the blocked case, quarantine, the gates
  openapi/    generated from the Zod contracts
```

## Where to go next

1. [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — every flow, with the
   deterministic/model boundary marked
2. [`docs/CONTRACTS.md`](docs/CONTRACTS.md) — the three typed contracts and the
   idempotency rules
3. [`DECISIONS.md`](DECISIONS.md) — the architectural decisions and why
4. `make show-sdk` — the Agents SDK wiring, in full
