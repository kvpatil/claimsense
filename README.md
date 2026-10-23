# ClaimSense

**The claims adjudication workflow, automated.**

Northwind Mutual's adjusters work a claim by hand across three systems —

| | | |
|---|---|---|
| **CMS** | Claims Management System | the claim, the first notice of loss, notes, decisions |
| **PAS** | Policy Administration System | policies, dates, coverages, limits, the policy wording |
| **DMS** | Document Management System | the files, and the text read out of them |

— reading the file, checking cover, finding the governing clause, working out
what is payable, and writing the decision. ClaimSense is that workflow
refactored into an automated pipeline.

**ClaimSense is not a claims management system.** It owns no system of record.
Northwind's CMS holds the claims and continues to; ClaimSense reads all three
systems and writes one thing back — a recommendation. Every acronym used
anywhere in this repository is expanded in [`docs/GLOSSARY.md`](docs/GLOSSARY.md).

What stays human is the **decision itself**: every outcome is produced as a
recommendation and a licensed adjuster confirms it before anything reaches a
claimant. That is a regulatory requirement and a design constraint, not a
hedge about the automation's quality.

```bash
make setup          # one-time
./week1_demo.sh     # the existing manual system
./week3_demo.sh     # the same workflow, automated
```

---

# Getting started

## 1. Prerequisites

| | Needed for | Check |
|---|---|---|
| **Docker** (running) | Postgres and the portal | `docker info` |
| **Python 3.11+** | the agent | `python3 -V` |
| [**uv**](https://docs.astral.sh/uv/) | creates the agent's virtualenv | `uv --version` |
| **Node 20+** | only if you run the portal *outside* Docker | `node -v` |

No AWS account and no API key. The whole thing runs on the mock brain — zero
network, zero spend — and that is the path CI measures, not a reduced one.

```bash
make doctor     # reports what is missing
```

## 2. Configure

```bash
cd claimsense
make setup
```

That does three things:

| | |
|---|---|
| `cp .env.example .env` | **wiring** — base URLs, the local database DSN, model ids. No secrets; safe on a screenshare. |
| `cp keys.env.example keys.env` | **secrets** — gitignored, mode `0600`. Leave every value blank for the demos. |
| `make venv` | the agent's virtualenv with `pytest`, which the Week 3 demo uses |

**You do not need to edit either file to run the demos.** Fill in `keys.env`
only when you want to exercise the live Bedrock path or the write-back to the
portal — see [Going further](#going-further).

## 3. Bring up the stack

```bash
docker compose up -d --wait
```

About 15 seconds from nothing. It starts Postgres, applies the three
client-system schemas, loads the synthetic seed, and serves the portal.

| | |
|---|---|
| Portal | <http://localhost:3200> — **Northwind Mutual, Claims Desk** |
| Postgres | `localhost:5433` *(not 5432 — see [Ports](#ports))* |

```bash
docker compose ps      # both should read (healthy)
```

---

# Week 1 — the existing system

```bash
./week1_demo.sh
```

Northwind has run Claims Desk for years. **There is no automation in it.** The
demo walks the current manual workflow and the problem the engagement exists to
solve.

It presses `[enter]` between sections. To run straight through:

```bash
NOPAUSE=1 ./week1_demo.sh
```

### What it shows

| Step | |
|---|---|
| 1 | Northwind's estate comes up |
| 2 | **The queue** — 60 claims, none worked, the open exposure |
| 3 | **One claim, three systems** — what assembling claim 4414 actually takes |
| 4 | **Searching the policy wording by hand** — the step with no real system behind it |
| 5 | **Where the time goes** — the blank decision form, and the ageing queue |

Step 4 is the one to watch. Searching the wording for **"water"** returns five
clauses, of which two decide the claim and three are noise — and one is an
*exception* to the other, which nothing in the portal tells you. Searching the
claimant's own word, **"leaking"**, returns **zero**, because the form says
"deterioration".

### Look around the portal yourself

<http://localhost:3200>

| Page | |
|---|---|
| Overview | the backlog, and the current process written out |
| Claims | the queue — every claim reads "not worked" |
| **Claims → 4414** | the workbench. The decision panel is a **blank form**: outcome, clause ids typed from memory, the payable amount worked out on paper |
| Policy wording | the manual search. Try `water`, then `leaking` |

> **Week 1 needs a clean slate.** The demo refuses to run if the database
> already holds recommendations — showing the manual workflow beside twenty
> agent decisions would be showing nothing. If you have run Week 3's
> write-back, reset with `make reset`.

---

# Week 3 — the same workflow, automated

```bash
./week3_demo.sh
```

Everything Week 1 showed an adjuster doing by hand, ClaimSense now does. Runs
entirely on the mock brain — no key, no network, no spend.

### What it shows

| Step | |
|---|---|
| 1 | **One claim end to end** — claim 4414, the water loss, traced |
| 2 | **`search_policy_clauses`** — the tool that replaces the manual search, on the claim that defeated it |
| 3 | **The boundary** — what is arithmetic, what is judgment, enforced by a test |
| 4 | **The blocked case** — a $17,500 approval becoming a human review |
| 5 | **Prompt injection** — in a document, and in the claimant's own words |
| 6 | **Arithmetic beats eloquence** — a plausible narrative denied by a date |
| 7 | **The gate** — 20 cases, all four outcomes, 5/5 adversarial |
| 8 | **The gate has teeth** — regress three cases, watch the exit code |
| 9 | **Driving it without the portal** |

Step 4 is the one M2 asks to see. Same claim, one flag apart:

| | Normal | `--tripwire` |
|---|---|---|
| Outcome | `APPROVE` | `MORE_INFO` |
| Settlement | **$17,500.00** | — |
| Citations | `HO3-I-A-1` | — |

```
⛔ coverage conclusion states a money-moving outcome with no policy citation
⛔ OUTPUT BLOCKED — not returned, not written back
✓ routed to a licensed adjuster instead
```

### Drive the agent yourself

```bash
make serve      # http://127.0.0.1:8080
```

A test client **served by the agent**, on its own port, with no portal
involved. Pick a claim, pick the seat to act as, tick *force the tripwire*, and
read the whole run: the narrative, the verdict, which clauses were *retrieved*
against which were *cited*, whether that seat may view and separately may
confirm, and the spans.

Worth trying: claim **4409** (injection in a document), **4420** (injection in
the claimant's own words), **4412** (a policy reference that does not resolve).

---

# Running the pieces

| Command | |
|---|---|
| `make verify` | the **$0 gate** — prerequisites, eval, 220 tests |
| `make agent CLAIM=4414` | work one claim, traced |
| `make tripwire` | the blocked case on its own |
| `make eval` / `make golden` | the gates CI runs |
| `make serve` | the agent test client on `:8080` |
| `make show-sdk` | the real Agents SDK wiring, printed |
| `make reset` | wipe decisions, back to the Week 1 state |
| `make down` | stop Postgres (`make clean` also drops the volume) |
| `make help` | everything |

---

# Going further

Both demos run with `keys.env` empty. Fill it in for:

**The write-back** — the recommendation landing in Claims Desk.

```bash
make keys          # mints three scoped keys straight into keys.env, mode 0600
cd agent && PYTHONPATH=src ../agent/.venv/bin/python -m claimsense_agent \
  run --claim 4414 --live --mock --write
```

Then open <http://localhost:3200/claims/4414> — the recommendation is there,
with the clause text it was grounded in and a confirm control that has not
been used. *(This is Week 4 territory; it works today.)*

**The live model** — the real Agents SDK over LiteLLM to AWS Bedrock. Put your
AWS credentials in `keys.env` and drop `--mock`. This spends money; the mock
path does not.

---

# Reference

## Ports

| | | Why |
|---|---|---|
| Portal | **3200** | Meridian's reference console holds 3100 |
| Postgres | **5433** | Meridian's holds 5432 — both are often up at once |
| Agent test client | **8080** | loopback only |

## What is code and what is judgment

| Deterministic — `agent/.../determinism/` | Model judgment — `agent/.../agents/` |
|---|---|
| identity, access control, who may confirm | reading the file: FNOL, notes, documents |
| policy dates: in force, lapse, reporting window | which clause governs — **must cite retrieved ids** |
| money: deductible, limits, coinsurance | what the fraud indicators amount to together |
| the fraud **score** arithmetic | the drafted decision and its rationale |

Enforced, not described: `agent/tests/test_boundary.py` walks the AST of every
module under `determinism/` and fails the build if one imports an agent SDK,
`litellm` or `boto3` — or if the money module grows a float literal.

A verdict the model reasoned to is stamped `source: "model"`. One a
deterministic check substituted is stamped `"deterministic_fallback"`. A
decision an adjuster typed unaided is `"manual_adjuster"`. They are never the
same kind of output.

## Synthetic data only

No production or personally identifiable data at any stage. Fixed seed (7731),
so every `make up` produces the same sixty claims. Email addresses use the
reserved `.invalid` and `.example` domains and can never route. The policy
corpus is synthetic wording modelled on the *shape* of an ISO-style form — not
any insurer's actual policy, and not to be used as one.

## Layout

```
agent/        the pipeline, determinism, retrieval, guardrails, evals, test client
platform/
  db/         the three client-system schemas + the synthetic seed generator
  web/        Claims Desk and the three system APIs (Next.js, JS + JSX)
docs/
  week1/      discovery — charter, stakeholders, success criteria, eval cases
  week2/      SoW, pricing, risk register, architecture, data shapes
  week3/      the automated workflow
  evidence/   captured runs: the blocked case, quarantine, the gates
  openapi/    generated from the Zod contracts
```

## Troubleshooting

| | |
|---|---|
| `docker daemon is not running` | start Docker Desktop |
| Week 1 refuses to run | `make reset` — it needs a clean slate |
| `pytest is not available` | `make venv` |
| Portal 500s on every page | the seed did not finish: `docker compose logs seed` |
| Agent 401s on `--live` | `make keys`, then retry |
| Port already in use | something else holds 3200/5433 — `make down`, or change `PORT` |

## Where to go next

1. [`docs/GLOSSARY.md`](docs/GLOSSARY.md) — **every acronym, expanded**
2. [`docs/week1/VALUE_STREAMS.md`](docs/week1/VALUE_STREAMS.md) — the workflows, who is in each, and where the automation lands
3. [`docs/week1/`](docs/week1/) · [`docs/week2/`](docs/week2/) · [`docs/week3/`](docs/week3/) — the milestone bundles
4. [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — every flow, with the boundary marked
5. [`docs/CONTRACTS.md`](docs/CONTRACTS.md) — the three contracts and the idempotency rules
6. [`DECISIONS.md`](DECISIONS.md) — what was decided, and what it cost
