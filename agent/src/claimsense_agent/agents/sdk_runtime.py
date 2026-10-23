"""The live path — OpenAI Agents SDK over LiteLLM to AWS Bedrock.

Imported ONLY when credentials are present and --mock was not passed, so the
$0 gate never needs these packages installed.

What is the same as the mock path, and this is the whole architectural claim:
the tools, the guardrails, the determinism modules, the scorecard and the
write-back. What changes is who reasons. If this file could be deleted and the
pipeline still produced all four outcomes, the seam is in the right place —
and it can, which is what `--mock` is.

Model routing is cost engineering, not tuning. The high-volume stages run on
the fast model; the smart model touches exactly one step — Coverage, where the
money is. See brain.STAGE_MODEL.
"""
from __future__ import annotations

import json
from typing import Any

from ..brain import MODEL_FAST, MODEL_SMART
from ..guardrails import (citation_tripwire, neutralise_narrative,
                          quarantine_poisoned)
from ..retrieval import Retriever
from . import coverage as coverage_stage
from . import evidence as evidence_stage
from . import triage as triage_stage


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
        bundle = claim_bundle(data, claim_id)
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
            # states them and never recalculates them.
            "clock": state.get("clock_facts", {}),
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


def build_agents(tools):
    """Triage ➜ Evidence ➜ Coverage, with the handoffs the SDK makes one line."""
    from agents import Agent
    from agents.extensions.models.litellm_model import LitellmModel

    load_claim, gather_evidence, search_policy_clauses = tools

    coverage = Agent(
        name="Coverage",
        instructions=coverage_stage.INSTRUCTIONS,
        model=LitellmModel(model=MODEL_SMART),   # the money step
        tools=[search_policy_clauses],
    )
    evidence = Agent(
        name="Evidence",
        instructions=evidence_stage.INSTRUCTIONS,
        model=LitellmModel(model=MODEL_FAST),
        tools=[gather_evidence],
        handoffs=[coverage],
    )
    triage = Agent(
        name="Triage",
        instructions=triage_stage.INSTRUCTIONS,
        model=LitellmModel(model=MODEL_FAST),
        tools=[load_claim],
        handoffs=[evidence],
    )
    return triage, evidence, coverage


async def run_live(data, claim_id, *, tracer, state: dict[str, Any]) -> str:
    """Drive the SDK pipeline and stream the spans.

    run_streamed rather than a blocking run: W15's note is that it survives
    restrictive client IAM where converse_stream does not, and first tokens
    reach the user sooner. Both matter in an enterprise estate.
    """
    import litellm
    # Required for the LiteLLM -> Bedrock bridge to carry tool-call history.
    # Without it the second turn loses the first turn's tool results and the
    # handoff chain silently degrades to three unrelated conversations.
    litellm.modify_params = True

    from agents import ItemHelpers, Runner, SQLiteSession, set_tracing_disabled

    # The SDK's own tracing uploads to OpenAI. This engagement runs in the
    # client's estate, so spans stay local — trace.py is the audit trail.
    set_tracing_disabled(True)

    state["retriever"] = Retriever(data.get_clauses())
    tools = build_tools(data, claim_id, state)
    triage, _, _ = build_agents(tools)

    # An adjuster's session survives a lunch break: kill the process, restart,
    # resume the same claim mid-investigation.
    session = SQLiteSession(f"claim-{claim_id}")

    result = Runner.run_streamed(
        triage, f"Work claim {claim_id} end to end and reach a coverage finding.",
        session=session, max_turns=20)

    current = "Triage"
    async for ev in result.stream_events():
        if ev.type == "agent_updated_stream_event":
            if ev.new_agent.name != current:
                with tracer.span(f"handoff: {current} ➜ {ev.new_agent.name}",
                                 kind="handoff") as t:
                    model = MODEL_SMART if ev.new_agent.name == "Coverage" else MODEL_FAST
                    t.kv("model", model.split("/")[-1])
                current = ev.new_agent.name
        elif ev.type == "run_item_stream_event" and ev.item.type == "message_output_item":
            text = ItemHelpers.text_message_output(ev.item).strip()
            if text:
                with tracer.span(f"{current}.output", kind="agent") as t:
                    for ln in text.splitlines():
                        t.event(ln)

    return result.final_output or ""


def enforce_output_guardrail(final_text: str, cited: list[str],
                             retrieved: list[str]):
    """The tripwire, on the live path.

    Deliberately the SAME function the mock path calls. A guardrail that is
    only enforced on one brain is not a control, and re-implementing it as an
    @output_guardrail decorator would be a second copy to keep in step.
    """
    return citation_tripwire(final_text, cited, retrieved)


SDK_REFERENCE = '''\
# ClaimSense on the OpenAI Agents SDK — the wiring, in full.
# Run it for real with:  claimsense-agent run --claim 4401 --live

import litellm
litellm.modify_params = True          # carry tool-call history over Bedrock

from agents import (Agent, Runner, SQLiteSession, function_tool,
                    input_guardrail, output_guardrail,
                    GuardrailFunctionOutput, set_tracing_disabled)
from agents.extensions.models.litellm_model import LitellmModel

from claimsense_agent.guardrails import (quarantine_poisoned,
                                         citation_tripwire)

set_tracing_disabled(True)            # spans stay in the client's estate

# --- tools: the agents' only route to a client system ----------------------
@function_tool
def load_claim() -> str: ...          # CMS: claim + first notice of loss
@function_tool
def gather_evidence() -> str: ...     # CMS + PAS + DMS, quarantine applied
@function_tool
def search_policy_clauses(query: str) -> str: ...   # PAS: BM25 over the corpus

# --- guardrails ------------------------------------------------------------
@input_guardrail                      # drop poisoned documents, fail closed
async def quarantine(ctx, agent, documents):
    q = quarantine_poisoned(documents)
    return GuardrailFunctionOutput(
        output_info={"quarantined": q.quarantined_ids},
        tripwire_triggered=False)     # quarantine, do not halt the run

@output_guardrail                     # uncited money claim -> BLOCK -> human
async def citations(ctx, agent, output):
    tw = citation_tripwire(output.statement, output.cited_clause_ids,
                           ctx.context["retrieved"])
    return GuardrailFunctionOutput(output_info=tw,
                                   tripwire_triggered=tw.triggered)

# --- the three agents, with model routing ----------------------------------
# Cost engineering: the smart model touches ONE step, the one where money moves.
coverage = Agent(name="Coverage", instructions=COVERAGE_INSTRUCTIONS,
                 model=LitellmModel(model=MODEL_SMART),
                 tools=[search_policy_clauses], output_guardrails=[citations])
evidence = Agent(name="Evidence", instructions=EVIDENCE_INSTRUCTIONS,
                 model=LitellmModel(model=MODEL_FAST),
                 tools=[gather_evidence], input_guardrails=[quarantine],
                 handoffs=[coverage])
triage   = Agent(name="Triage", instructions=TRIAGE_INSTRUCTIONS,
                 model=LitellmModel(model=MODEL_FAST),
                 tools=[load_claim], handoffs=[evidence])

# --- run: sessions persist, so an investigation survives a lunch break ------
session = SQLiteSession(f"claim-{claim_id}")
result  = Runner.run_streamed(triage, f"Work claim {claim_id} end to end.",
                              session=session, max_turns=20)

# Adjudication, settlement arithmetic, eligibility and access control are NOT
# agents. They are deterministic code the pipeline runs around this chain —
# see claimsense_agent/determinism/.
'''
