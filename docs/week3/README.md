# Week 3 — Building the automated workflow

**Submission bundle.** The manual workflow Week 1 documented, refactored into
an automated pipeline on the OpenAI Agents SDK, under change control.

---

## See it

```bash
./week3_demo.sh     # the full walkthrough
make serve          # the agent's own test client on :8080
make verify         # the $0 gate: eval + 308 tests
```

---

## Milestones, and what proves each

| Milestone | Evidence |
|---|---|
| Agent set on the Agents SDK with strict typed outputs | `agents/sdk_runtime.py` · `contracts.py` · `make show-sdk` · [tests](../../agent/tests/test_sdk_runtime.py) |
| Container build, single-command start | `docker compose up` · [`../../docker-compose.yml`](../../docker-compose.yml) |
| Retrieval citing the clause ids actually retrieved | `search_policy_clauses` · [`01-normal-run.txt`](../evidence/01-normal-run.txt) |
| CI where a failing eval gate blocks the image push | [`eval-gate.yml`](../../.github/workflows/eval-gate.yml) — `needs: [test, eval, integration]` |
| All four outcomes, model verdicts distinguishable from fallback | [`05-eval-gate.txt`](../evidence/05-eval-gate.txt) |
| **The blocked case, shown** | [`02-blocked-by-tripwire.txt`](../evidence/02-blocked-by-tripwire.txt) |

---

## Which brain runs

Two brains, one pipeline. The branch is the only one in `run_pipeline`;
everything downstream of it — the guardrails, the risk interpretation, the
adjudication, the override, the routing, the checks and the scorecard — runs
identically whichever brain produced the three stage outputs.

| | `--mock` (the default) | `--live` with credentials |
|---|---|---|
| Who reasons | deterministic reasoners in `agents/*.py` | three `Agent`s on the OpenAI Agents SDK |
| Cost | $0, no key, no network | real Bedrock spend |
| Used by | CI, the eval gate, every milestone number | demos and the live-path evidence |

```bash
make venv-llm                              # installs the SDK extra
#  then put AWS credentials in keys.env
cd agent && .venv/bin/python -m claimsense_agent run --claim 4401 --live
```

**Three agents, not five.** Triage, Evidence and Coverage are the stages where
a different reading changes the answer, so those are the agents. Risk and the
adjudicator stay in code: the fraud score is arithmetic, and the adjudicator is
the precedence ladder that *computes* `source` — a model there would erase the
distinction M2 asks to be visible. Both module docstrings carry the prompt they
would have had, and a test asserts neither carries a live one.

**Not a handoff chain.** `build_agents` passes no `handoffs=`. The guardrails
sit *between* the stages — quarantine on the Evidence output, the citation
tripwire on the Coverage output — so the pipeline needs a validated typed
result at every boundary, and a handoff chain yields only the last agent's
`output_type`. One `SQLiteSession` per claim carries context across the three
runs instead.

**What the model is allowed to have decided.** Each stage's output is
reconciled afterwards: the model keeps its judgment (peril, severity, finding,
statement, citations, confidence) and code overwrites everything that was never
its to set — the clock dates, the systems inventory, and above all
`retrieved_clause_ids`, which is the allowlist the citation tripwire checks
against. A model able to set its own allowlist could cite anything and the
guardrail would wave it through. `test_sdk_runtime.py` asserts it cannot.

**When the model cannot answer.** A stage whose output fails validation is
retried once, then falls back to its deterministic reasoner — and the verdict
is stamped `deterministic_fallback`, because a decision resting on a mock
coverage opinion is not a model decision. The scorecard's `brain=` line reports
what actually reasoned (`llm`, `llm (partial: coverage fell back)`, or `mock`),
not what was configured. A non-retryable failure — bad credentials, an
unavailable inference profile — fails the stage once rather than burning six
round trips on a request that could never succeed.

**Mock and live will not always agree.** The mock coverage reasoner is phrase
matching and will miss a paraphrase it was not given; that divergence is
information about the mock, not a live-path defect. The eval suites are
asserted against `--mock` on purpose — a gate whose expectations move with a
model is not a gate.

---

## The pipeline

Northwind's workflow, stage for stage. The harness is kept; the tools,
instructions and guardrail targets are the domain.

| Stage | Replaces | Model |
|---|---|---|
| **Triage** | opening the file and sizing it against the clock | Haiku 4.5 |
| **Evidence** | the three-tab assembly — CMS, PAS, DMS | Haiku 4.5 |
| **Coverage** | searching the policy wording and deciding which clause governs | **Sonnet 4.5** |
| **Risk** | reading the fraud indicators together | Haiku 4.5 |
| **Adjudicate** | writing the decision | Haiku 4.5 |

**Model routing is a deliverable, not an optimisation.** Sonnet touches exactly
one step — the one where money moves. Per-run cost is recorded in
`platform.agent_runs`.

### `search_policy_clauses`

The tool that replaces the adjuster's manual search. Same corpus the portal
exposes at `/policy`, three differences:

- pre-filtered by product and peril, so an AUTO racing exclusion can never
  surface on a homeowners water claim
- ranked against the claimant's own narrative
- **the ids it returns are recorded**, which is what makes a citation checkable

Week 1 measured the manual version's cost: searching "water" returns five
clauses of which two decide the claim; searching the claimant's own word
"leaking" returns **zero**, because the form says "deterioration".

---

## The blocked case

M2 asks for it explicitly. Same claim, one flag apart:

| | Normal | `--tripwire` |
|---|---|---|
| Outcome | `APPROVE` | `MORE_INFO` |
| Settlement | **$17,500.00** | — |
| Citations | `HO3-I-A-1` | — |
| Guardrails | none | `citation_tripwire` |

```
⛔ coverage conclusion states a money-moving outcome with no policy citation
⛔ OUTPUT BLOCKED — not returned, not written back
✓ routed to a licensed adjuster instead
```

Reachable from the CLI (`make tripwire`) and from the test client, because a
control nobody has watched fire is a control nobody should trust.

---

## The four guardrails

| | Fires when | Result |
|---|---|---|
| **Quarantine** (input) | a document carries text aimed at a model | dropped before model context, logged. Fails closed. |
| **Citation tripwire** (output) | a money-moving claim is uncited, or cites a clause never retrieved | **blocked**, routed to a human |
| **Determinism override** (output) | the model approves on a lapsed policy or over a limit | the check wins; re-stamped `deterministic_fallback` |
| **PII scan** (output) | personal data appears in a drafted output | blocked — the synthetic-only invariant |

Quarantine **drops rather than sanitises**, and it has a cost the system pays:
on claim 4409 the poisoned file is the only estimate, so the claim becomes
`MORE_INFO` rather than `APPROVE`. An attacker cannot complete a claim file by
submitting a hostile document.

**Claim 4420 is the hard case.** The injection is in the claimant's own first
notice of loss, which is evidence and must be read. It is fenced as untrusted
rather than dropped, and the citation tripwire is what makes a successful
injection harmless. It still returns a cited `DENY`.

---

## The gate

```
pass rate      100%  (20/20)   threshold 90%
outcomes seen  {'APPROVE': 5, 'DENY': 8, 'MORE_INFO': 5, 'SIU_REFERRAL': 2}
adversarial    5/5 held
GATE PASSED
```

Three ways to fail: the rate, **an outcome never produced**, or any `ADV-*`
regression on the golden gate at zero tolerance.

It exits non-zero on each. That has its own test —
`agent/tests/test_gate_exit_code.py` runs the CLI as a subprocess — because the
gate once printed `GATE FAILED` in red and exited **0**, which would have let
CI go green and push the image.

---

## Testing the agent alone

```bash
make serve     # http://127.0.0.1:8080
```

Served **by the agent**, stdlib only. Separate port, separate process, no
Next.js and no portal database. If it works with Claims Desk down, the pipeline
is genuinely independent of it.

Returns the whole run, not just the answer: narrative, structured verdict,
retrieved-versus-cited clauses, whether the chosen seat may view and separately
may confirm, the code-versus-judgment breakdown, the checks and the spans.

---

## Not in Week 3 scope

Week 3 delivers the capability **standalone**. These put ClaimSense inside
Northwind's workflow and belong to Week 4:

| | |
|---|---|
| Recommendations reaching an adjuster in Claims Desk | the write-back into the claims management system |
| The confirm / override control | a licensed adjuster acting on a recommendation |
| The two-adjuster confirmation test | the Week 4 acceptance gate |
| **MCP** | the governed door for tool access — W16 |
| Identity and RBAC at the integration boundary | OAuth2 on-behalf-of, scoped per seat |

### Two of those are built early, and gated

The write-back (`--write`) and the portal's confirm control **exist and are
tested**. They are held behind `CLAIMSENSE_STAGE`, which defaults to `week3`:

```bash
make agent CLAIM=4414                     # the Week 3 deliverable
… run --claim 4414 --live --mock --write  # refused, naming the variable
CLAIMSENSE_STAGE=week4 … --write          # the Week 4 path
```

At `week3` the portal shows a recommendation with a note where the confirm
control will be, rather than hiding it — an absent control reads as a missing
feature; a labelled one reads as a scope boundary.

Building something early is not a reason to claim it in the wrong week. See
[`../../agent/src/claimsense_agent/stage.py`](../../agent/src/claimsense_agent/stage.py).

**Working a claim by hand is unaffected in every stage** — that is the Week 1
capability and it must keep working.
