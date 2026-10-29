"""The live path — OpenAI Agents SDK over LiteLLM to AWS Bedrock.

Imported ONLY when credentials are present and --mock was not passed, so the
$0 gate never needs these packages installed.

What is the same as the mock path, and this is the whole architectural claim:
the tools, the guardrails, the determinism modules, the scorecard and the
write-back. What changes is who reasons. If this file could be deleted and the
pipeline still produced all four outcomes, the seam is in the right place —
and it can, which is what `--mock` is.

Three agents, driven ONE STAGE AT A TIME rather than as an SDK handoff chain.
That is a deliberate choice and it is not the shape the SDK's own examples
show, so it is worth saying why:

  * The guardrails sit BETWEEN the stages. quarantine_poisoned gates the
    Evidence output and citation_tripwire gates the Coverage output. A handoff
    chain surfaces only the LAST agent's `output_type`, so there would be
    nothing typed to gate at the Evidence boundary.
  * An agent carrying both `output_type` and `handoffs` leaves the model to
    choose between emitting its structured output and calling the handoff
    tool. That non-determinism is not acceptable underneath an eval gate.

Continuity across the three runs comes from one SQLiteSession per claim, so
each stage still sees what the previous stage established — the thing a handoff
would have given us — without surrendering the stage boundary to the model.

Model routing is cost engineering, not tuning. The high-volume stages run on
the fast model; the smart model touches exactly one step — Coverage, where the
money is. See brain.STAGE_MODEL.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any, Callable

from ..contracts import CoverageOpinion, EvidenceBundle, TriageDecision
from ..guardrails import neutralise_narrative
from ..retrieval import Retriever
from . import coverage as coverage_stage
from . import evidence as evidence_stage
from . import triage as triage_stage

# Bedrock's Converse API has no response_format / strict-JSON-schema feature,
# so asking the SDK for a provider-enforced strict schema there buys nothing
# and can be rejected outright. Non-strict is the default for that reason —
# and it costs NOTHING in enforcement: the SDK validates the model's JSON
# against the dataclass either way and raises ModelBehaviorError on a
# mismatch, which is what _stage below catches. Set CLAIMSENSE_STRICT_SCHEMA=1
# on a provider that does enforce schemas server-side (OpenAI does).
STRICT_SCHEMA = os.environ.get("CLAIMSENSE_STRICT_SCHEMA", "") in ("1", "true", "yes")


def _init_litellm() -> None:
    """Settings the LiteLLM -> Bedrock bridge needs, in one place."""
    import litellm
    # Required for the bridge to carry tool-call history. It mattered for a
    # handoff chain and it matters just as much here: the three stages share
    # one session, so turn two must still be able to see turn one's tool
    # results.
    litellm.modify_params = True
    # LiteLLM prints a multi-line "get help" banner to stderr on every error.
    # The trace IS the audit artefact for this engagement; a provider's
    # support link in the middle of it is noise, and the exception type and
    # message are already recorded on the failing span.
    litellm.suppress_debug_info = True


@dataclass
class StageResults:
    """The three typed stage outputs, plus WHO produced each one.

    `brains` is the honest provenance record. A stage that fell back to its
    mock reasoner is not a model judgment, and the adjudicator uses this to
    refuse to stamp such a verdict `model`.
    """
    triage: TriageDecision
    evidence: EvidenceBundle
    coverage: CoverageOpinion
    brains: dict[str, str] = field(default_factory=dict)

    @property
    def all_model(self) -> bool:
        return all(v == "model" for v in self.brains.values())

    def fell_back(self) -> list[str]:
        return [k for k, v in self.brains.items() if v != "model"]


def build_tools(data, claim_id: int | str, state: dict[str, Any]):
    """The agents' hands.

    Plain functions, wrapped by the SDK. They are the SAME functions the mock
    path calls — the model chooses WHEN to call them, it does not change what
    they do, and it cannot reach a client system except through one of these.

    `state` accumulates what the guardrails and the scorecard need, because a
    model's prose is not a data structure and the pipeline must not have to
    parse one back out of it.
    """
    from agents import function_tool

    @function_tool
    def load_claim() -> str:
        """Load the claim, the first notice of loss and the policy."""
        from ..systems import claim_bundle
        bundle = state.get("bundle") or claim_bundle(data, claim_id)
        state["bundle"] = bundle
        claim, policy = bundle["claim"], bundle.get("policy")
        fnol = bundle.get("fnol") or []
        narrative = fnol[0]["narrative"] if fnol else ""
        # The FNOL cannot be dropped — it is the claimant's own evidence — so
        # an injection inside it is fenced rather than removed, and the agent
        # instructions say content inside the fence is reported, never obeyed.
        safe = neutralise_narrative(narrative)
        state["narrative_neutralised"] = safe.neutralised
        return json.dumps({
            "claim_id": claim["claim_id"],
            "peril": claim["peril"],
            "date_of_loss": claim["date_of_loss"],
            "reported_at": claim["reported_at"],
            "claimed_amount_cents": claim["claimed_amount_cents"],
            "loss_state": claim.get("loss_state"),
            "policy": None if not policy else {
                "product": policy["product"],
                "status": policy["status"],
                "effective_date": policy["effective_date"],
                "expiration_date": policy["expiration_date"],
                "lapse_date": policy.get("lapse_date"),
            },
            # Supplied as FACTS. determinism/clock.py computed these; the model
            # states them and never recalculates them. Severity is judged
            # against the limit, so the limit is a fact too.
            "clock": state.get("clock_facts", {}),
            "governing_limit_cents": state.get("governing_limit_cents"),
            "first_notice_of_loss": safe.text,
        }, default=str)

    @function_tool
    def gather_evidence() -> str:
        """Read all three client systems and report what is on file."""
        bundle = state.get("bundle") or {}
        ev = evidence_stage.run(bundle)
        state["evidence"] = ev
        return json.dumps({
            "systems_answered": ev.source_systems,
            "sufficient": ev.sufficient,
            "documents_on_file": ev.documents_on_file,
            "missing_documents": ev.missing_documents,
            "quarantined_count": len(ev.quarantined_document_ids),
            "facts": ev.facts[:12],
        })

    @function_tool
    def search_policy_clauses(query: str) -> str:
        """Search the policy wording and return the clauses that govern.

        This is the tool that replaces the adjuster's manual search of the
        form. The manual version is still in the portal at /policy: type words
        and read what comes back, unranked, with no knowledge of the claim.

        This one is handed the claim's product and peril, pre-filters the
        corpus on both, ranks the rest against the claimant's own narrative,
        and RECORDS the ids it returned — which is what makes a citation
        checkable afterwards. Cite only ids this tool returned.
        """
        bundle = state.get("bundle") or {}
        policy = bundle.get("policy")
        claim = bundle["claim"]
        retriever: Retriever = state["retriever"]
        hits = retriever.search(
            query, product=policy["product"] if policy else None,
            peril=claim["peril"], top_k=8)
        ids = [h.clause_id for h in hits]
        # Pin the governing grant and the general provisions. BM25 ranks on
        # words and a grant of coverage never names a peril, so the clause a
        # claim most needs cannot be retrieved by score. See coverage.run.
        for pin in filter(None, [
                coverage_stage._GRANTS.get(
                    (policy["product"] if policy else "HO3", claim["peril"])),
                "ALL-GEN-1", "ALL-GEN-2"]):
            if pin not in ids and retriever.by_id(pin):
                ids.append(pin)

        state.setdefault("retrieved", []).extend(i for i in ids
                                                 if i not in state.get("retrieved", []))
        clauses = [retriever.by_id(i) for i in ids]
        return json.dumps([
            {"clause_id": c["clause_id"], "title": c["title"],
             "type": c["clause_type"], "body": c["body"]}
            for c in clauses if c])

    return load_claim, gather_evidence, search_policy_clauses


def build_agents(tools, *, fast: str, smart: str, model_factory=None):
    """The three agents, each with a STRICT TYPED OUTPUT.

    `output_type=` is the milestone requirement and it is not decoration: the
    SDK validates the model's JSON against the dataclass and raises
    ModelBehaviorError when it does not fit, so a stage either returns a
    well-formed TriageDecision / EvidenceBundle / CoverageOpinion or it
    returns nothing at all. There is no half-parsed middle state for the
    pipeline to guess at.

    No `handoffs=`. See the module docstring — the guardrails live between the
    stages, and an agent holding both output_type and handoffs lets the model
    choose which to emit.
    """
    from agents import Agent, AgentOutputSchema

    load_claim, gather_evidence, search_policy_clauses = tools

    if model_factory is None:
        # The only place a provider is named. `model_factory` is a seam for
        # tests: it lets the SDK loop — tool dispatch, output_type validation,
        # session, reconcile — be driven offline with a scripted model, so
        # "the agents run on the Agents SDK" is checked on every commit rather
        # than only by whoever happens to hold Bedrock credentials.
        from agents.extensions.models.litellm_model import LitellmModel
        model_factory = lambda name: LitellmModel(model=name)   # noqa: E731

    def typed(t):
        return AgentOutputSchema(t, strict_json_schema=STRICT_SCHEMA)

    coverage = Agent(
        name="Coverage",
        instructions=coverage_stage.INSTRUCTIONS,
        model=model_factory(smart),               # the money step
        tools=[search_policy_clauses],
        output_type=typed(CoverageOpinion),
    )
    evidence = Agent(
        name="Evidence",
        instructions=evidence_stage.INSTRUCTIONS,
        model=model_factory(fast),
        tools=[gather_evidence],
        output_type=typed(EvidenceBundle),
    )
    triage = Agent(
        name="Triage",
        instructions=triage_stage.INSTRUCTIONS,
        model=model_factory(fast),
        tools=[load_claim],
        output_type=typed(TriageDecision),
    )
    return triage, evidence, coverage


# ---------------------------------------------------------------------------
# Reconciliation: which fields the model is ALLOWED to have decided.
#
# This is the deterministic/judgment boundary, enforced after the fact rather
# than hoped for. The model returns a whole dataclass because that is the unit
# the SDK validates, but most of those fields are not its to set — they were
# computed in code before it ran, or recorded by a tool while it ran. Each
# function below keeps the model's judgment and overwrites everything else.
#
# This is a security property, not tidiness. `retrieved_clause_ids` is the
# allowlist the citation tripwire checks against; if the model could set it,
# the model could widen its own allowlist and cite anything it liked.
# ---------------------------------------------------------------------------

def _reconcile_triage(out: TriageDecision, *, state) -> TriageDecision:
    """Model decides: peril, product, severity, rationale, confidence.
    Code decides: the claim id and every date on the fair-claims clock.
    """
    ck = state["clock_facts"]
    claim = state["bundle"]["claim"]
    return replace(
        out,
        claim_id=int(claim["claim_id"]),
        ack_due_at=ck["ack_due_at"],
        decision_due_at=ck["decision_due_at"],
        clock_status=ck["clock_status"],
        hours_to_decision_deadline=ck["hours_to_decision_deadline"],
    )


def _reconcile_evidence(out: EvidenceBundle, *, state) -> EvidenceBundle:
    """Model decides: the `facts` summary, in its own words.
    Code decides: everything else — which systems answered, what is on file,
    what is missing and what was quarantined are READS, not opinions.
    """
    tool_bundle: EvidenceBundle | None = state.get("evidence")
    if tool_bundle is None:
        # The agent answered without calling gather_evidence. Nothing it said
        # about the three systems can be trusted, so treat the stage as failed
        # rather than accepting an inventory nobody took.
        raise ValueError("Evidence agent returned without calling gather_evidence")
    return replace(tool_bundle, facts=out.facts or tool_bundle.facts)


def _reconcile_coverage(out: CoverageOpinion, *, state) -> CoverageOpinion:
    """Model decides: finding, statement, cited_clause_ids, confidence.
    Code decides: the retrieval allowlist, and the guardrail's own verdict.
    """
    claim = state["bundle"]["claim"]
    return replace(
        out,
        claim_id=int(claim["claim_id"]),
        # The tool's record of what it actually returned — never the model's
        # claim about it. This is what makes citation_tripwire meaningful.
        retrieved_clause_ids=list(state.get("retrieved", [])),
        # The tripwire has not run yet. A model asserting it was not blocked
        # would be grading its own homework.
        blocked=False,
        tripwire_reason=None,
    )


async def _drive(agent, prompt: str, *, session, tracer, label: str, model: str):
    """One Runner.run_streamed, with the tool calls traced as they happen."""
    from agents import ItemHelpers, Runner

    result = Runner.run_streamed(agent, prompt, session=session, max_turns=8)

    with tracer.span(f"{label}: {agent.name} on {model.split('/')[-1]}",
                     kind="agent") as t:
        async for ev in result.stream_events():
            if ev.type != "run_item_stream_event":
                continue
            item = ev.item
            if item.type == "tool_call_item":
                t.event(f"calling {getattr(item.raw_item, 'name', 'tool')}",
                        level="tool")
            elif item.type == "tool_call_output_item":
                t.event(f"tool returned {len(str(item.output))} chars",
                        level="tool")
            elif item.type == "message_output_item":
                # With output_type set this is the structured JSON, which the
                # pipeline prints properly from the typed object. Record only
                # that it arrived — dumping raw JSON into the trace buries the
                # tool calls that are the interesting part.
                text = ItemHelpers.text_message_output(item).strip()
                if text:
                    t.event(f"returned {len(text)} chars of structured output",
                            level="info")

    if result.final_output is None:
        raise ValueError(f"{agent.name} produced no final output")
    return result.final_output


def _is_retryable(exc: Exception) -> bool:
    """Is a second attempt worth the latency?

    Retrying a bad credential or an unavailable model is six wasted round
    trips across three stages and seconds of latency on a run that could
    never have succeeded. Only two classes of failure earn a retry:

      * ModelBehaviorError — the model returned JSON that did not fit the
        dataclass. A second sample genuinely might.
      * a transient provider fault — throttling, timeout, 5xx.

    Everything else (auth, permission, unknown model, malformed request) is a
    configuration problem. It will fail identically the second time, so the
    stage fails once and says what was wrong.
    """
    from agents.exceptions import ModelBehaviorError
    if isinstance(exc, ModelBehaviorError):
        return True
    try:
        from litellm import exceptions as le
        return isinstance(exc, (le.RateLimitError, le.Timeout,
                                le.APIConnectionError, le.InternalServerError,
                                le.ServiceUnavailableError))
    except Exception:                     # litellm absent or restructured
        return False


async def _stage(name: str, agent, prompt: str, *, session, tracer, model: str,
                 reconcile: Callable, fallback: Callable, brains: dict[str, str],
                 attempts: int = 2):
    """Run one stage; retry a retryable failure, then fall back.

    The fallback IS the milestone: "model-generated verdicts distinguishable
    from deterministic fallback output". A stage that could not produce a
    valid typed result is recorded as `fallback`, the adjudicator refuses to
    stamp the verdict `model`, and the scorecard says so. The alternative —
    retrying forever, or accepting a malformed output — would either hang the
    run or quietly launder a bad result as a good one.
    """
    last: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            out = await _drive(agent, prompt, session=session, tracer=tracer,
                               label=name, model=model)
            result = reconcile(out)
            brains[name] = "model"
            return result
        except Exception as exc:          # SDK, reconcile and provider faults
            last = exc
        retry = attempt < attempts and _is_retryable(last)
        with tracer.span(f"{name}: attempt {attempt} failed", kind="guardrail") as t:
            t.event(f"{type(last).__name__}: {str(last)[:200]}", level="warn")
            if not retry:
                t.event("not retryable — this would fail identically",
                        level="warn")
        if not retry:
            break

    with tracer.span(f"{name}: deterministic fallback", kind="code") as t:
        t.event("the model could not produce a valid typed output; the "
                "deterministic reasoner stands in and the verdict will be "
                "stamped deterministic_fallback", level="block")
        t.kv("cause", type(last).__name__ if last else "unknown")
    brains[name] = "fallback"
    return fallback()


async def run_live_stages(data, claim_id, *, cfg, tracer, state: dict[str, Any],
                          now: datetime | None = None,
                          governing_limit_cents: int | None = None,
                          model_factory=None) -> StageResults:
    """Drive Triage ➜ Evidence ➜ Coverage on the SDK and return typed results.

    run_streamed rather than a blocking run: W15's note is that it survives
    restrictive client IAM where converse_stream does not, and first tokens
    reach the user sooner. Both matter in an enterprise estate.
    """
    if model_factory is None:
        _init_litellm()

    from agents import SQLiteSession, set_tracing_disabled

    # The SDK's own tracing uploads to OpenAI. This engagement runs in the
    # client's estate, so spans stay local — trace.py is the audit trail.
    set_tracing_disabled(True)

    from ..determinism import clock
    from ..systems import claim_bundle

    bundle = claim_bundle(data, claim_id)
    claim = bundle["claim"]
    ck = clock.compute(claim["reported_at"], state=claim.get("loss_state", ""),
                       now=now)

    # The deterministic facts the agents are HANDED rather than asked to work
    # out. load_claim serves these to the Triage agent verbatim.
    state["bundle"] = bundle
    state["governing_limit_cents"] = governing_limit_cents
    state["clock_facts"] = {
        "ack_due_at": ck.ack_due_at.isoformat(),
        "decision_due_at": ck.decision_due_at.isoformat(),
        "clock_status": ck.status,
        "hours_to_decision_deadline": round(ck.hours_to_decision, 1),
        "ack_breached": ck.ack_breached,
    }
    state["retriever"] = Retriever(data.get_clauses())
    state.setdefault("retrieved", [])

    tools = build_tools(data, claim_id, state)
    triage_agent, evidence_agent, coverage_agent = build_agents(
        tools, fast=cfg.fast, smart=cfg.smart, model_factory=model_factory)

    # What carries context from one stage to the next, now that there is no
    # handoff doing it: Coverage can see what Triage established without the
    # orchestrator having to re-summarise it into a prompt.
    #
    # In memory, which is SQLiteSession's default and is the right choice
    # here: the pipeline is one process working one claim, and a session
    # persisted to disk would make a second run of the same claim resume the
    # first one's conversation — nondeterminism the eval gate cannot have.
    # Passing a db_path would give cross-process resume (close the laptop
    # mid-investigation, pick the claim up later), which is a product feature
    # for Week 4 rather than something this pipeline needs.
    session = SQLiteSession(f"claim-{claim_id}")

    brains: dict[str, str] = {}

    triage = await _stage(
        "triage", triage_agent,
        f"Work claim {claim_id}. Classify it and state the clock.",
        session=session, tracer=tracer, model=cfg.fast,
        reconcile=lambda o: _reconcile_triage(o, state=state),
        fallback=lambda: triage_stage.run(
            bundle, now=now, governing_limit_cents=governing_limit_cents),
        brains=brains)

    evidence = await _stage(
        "evidence", evidence_agent,
        "Gather the evidence on this claim across all three client systems.",
        session=session, tracer=tracer, model=cfg.fast,
        reconcile=lambda o: _reconcile_evidence(o, state=state),
        fallback=lambda: state.get("evidence") or evidence_stage.run(bundle),
        brains=brains)

    coverage = await _stage(
        "coverage", coverage_agent,
        "Decide whether this loss is covered under the policy form. "
        "Cite the clause ids you were given.",
        session=session, tracer=tracer, model=cfg.smart,
        reconcile=lambda o: _reconcile_coverage(o, state=state),
        fallback=lambda: coverage_stage.run(bundle, state["retriever"]),
        brains=brains)

    return StageResults(triage=triage, evidence=evidence, coverage=coverage,
                        brains=brains)


def enforce_output_guardrail(final_text: str, cited: list[str],
                             retrieved: list[str]):
    """The tripwire, on the live path.

    Deliberately the SAME function the mock path calls. A guardrail that is
    only enforced on one brain is not a control, and re-implementing it as an
    @output_guardrail decorator would be a second copy to keep in step.
    """
    from ..guardrails import citation_tripwire
    return citation_tripwire(final_text, cited, retrieved)


SDK_REFERENCE = '''\
# ClaimSense on the OpenAI Agents SDK — the wiring, in full.
# Run it for real with:  claimsense-agent run --claim 4401 --live

import litellm
litellm.modify_params = True          # carry tool-call history over Bedrock

from agents import (Agent, AgentOutputSchema, Runner, SQLiteSession,
                    function_tool, set_tracing_disabled)
from agents.extensions.models.litellm_model import LitellmModel

from claimsense_agent import brain
from claimsense_agent.contracts import (TriageDecision, EvidenceBundle,
                                        CoverageOpinion)

set_tracing_disabled(True)            # spans stay in the client's estate

# --- tools: the agents' only route to a client system ----------------------
@function_tool
def load_claim() -> str: ...          # CMS: claim + first notice of loss
@function_tool
def gather_evidence() -> str: ...     # CMS + PAS + DMS, quarantine applied
@function_tool
def search_policy_clauses(query: str) -> str: ...   # PAS: BM25 over the corpus

# --- the three agents: STRICT TYPED OUTPUTS, model routing -----------------
# output_type= is enforcement, not decoration: the SDK validates the model's
# JSON against the dataclass and raises ModelBehaviorError on a mismatch.
# Cost engineering: the smart model touches ONE step, the one where money moves.
def typed(t):
    return AgentOutputSchema(t, strict_json_schema=False)   # Bedrock: see module

cfg = brain.detect(force_mock=False)   # resolves CLAIMSENSE_MODEL_* at runtime

coverage = Agent(name="Coverage", instructions=COVERAGE_INSTRUCTIONS,
                 model=LitellmModel(model=cfg.for_stage("coverage")),
                 tools=[search_policy_clauses],
                 output_type=typed(CoverageOpinion))
evidence = Agent(name="Evidence", instructions=EVIDENCE_INSTRUCTIONS,
                 model=LitellmModel(model=cfg.for_stage("evidence")),
                 tools=[gather_evidence],
                 output_type=typed(EvidenceBundle))
triage   = Agent(name="Triage", instructions=TRIAGE_INSTRUCTIONS,
                 model=LitellmModel(model=cfg.for_stage("triage")),
                 tools=[load_claim],
                 output_type=typed(TriageDecision))

# --- run: ONE STAGE AT A TIME, not an SDK handoff chain ---------------------
# The guardrails sit BETWEEN the stages (quarantine on Evidence, the citation
# tripwire on Coverage), so the pipeline needs a typed result at EVERY
# boundary — a handoff chain yields only the last agent's output_type. One
# shared session gives each stage the previous stage's context, which is what
# the handoff would have given us, without letting the model decide when a
# stage ends.
session = SQLiteSession(f"claim-{claim_id}")
for agent in (triage, evidence, coverage):
    result = Runner.run_streamed(agent, PROMPT[agent.name],
                                 session=session, max_turns=8)
    async for ev in result.stream_events():
        ...                           # tool calls -> trace.py spans
    typed_out = result.final_output    # a validated dataclass, or nothing

# Each stage is then RECONCILED: the model keeps its judgment (peril,
# severity, finding, statement, citations) and code overwrites what was never
# its to decide — the clock dates, the systems inventory, and above all
# retrieved_clause_ids, which is the allowlist the tripwire checks against.
# A model that could set its own allowlist could cite anything it liked.

# On ModelBehaviorError: retry once, then fall back to the deterministic
# reasoner for that stage and stamp the verdict deterministic_fallback.

# Adjudication, settlement arithmetic, the fraud score, eligibility and access
# control are NOT agents. They are deterministic code the pipeline runs around
# this chain — see claimsense_agent/determinism/.
'''
