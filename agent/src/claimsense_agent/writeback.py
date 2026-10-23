"""The complete circle — the recommendation lands in the product.

The pipeline produces a RunResult. On its own that is a terminal trace, and a
terminal trace is a demo. This module is what makes it an engagement: the
recommendation becomes a row in the claims system, where an adjuster finds it
in their own queue.

What is written is a RECOMMENDATION. The decision row lands with confirmed_by
NULL and stays that way until a licensed adjuster confirms it through the
console or the confirm endpoint. Nothing here decides anything.

Writes go through the CMS HTTP contract rather than straight to Postgres, on
purpose: the contract is where validation, idempotency, scope and the audit
row live, and an agent that bypassed it would be exercising a path no real
integration has.
"""
from __future__ import annotations

import os
import uuid
from typing import Any

from .contracts import RunResult
from .systems import ClaimsData, SystemError_


def idempotency_key(result: RunResult) -> str:
    """Stable per (claim, run).

    Keyed on the trace id so a retry of THIS run replays rather than writing a
    second recommendation, while a genuinely new run on the same claim is a
    new key and a new row. Keying on claim_id alone would make the second
    reading of a claim silently return the first one's answer.
    """
    return f"claimsense-{result.claim_id}-{result.trace_id}"


def decision_payload(result: RunResult) -> dict[str, Any]:
    v = result.verdict
    return {
        "outcome": v.outcome,
        # The milestone requirement, carried across the wire. The contract
        # rejects a body that omits it.
        "source": v.source,
        "rationale": v.rationale,
        "cited_clause_ids": list(v.cited_clause_ids),
        "settlement_cents": v.settlement_cents,
        "confidence": round(float(v.confidence), 3),
        "trace_id": result.trace_id,
    }


def write_back(data: ClaimsData, result: RunResult, *, tracer) -> dict[str, Any] | None:
    """Record the recommendation, and any document requests it implies."""
    payload = decision_payload(result)
    key = idempotency_key(result)

    with tracer.span("write_back: recommendation ➜ claims management",
                     kind="write") as t:
        if data.mock:
            t.event("mock data backend — nothing written. Use --live to land it "
                    "in the claims system.", level="warn")
            return None
        try:
            out = data.record_decision(result.claim_id, payload, key)
        except SystemError_ as exc:
            t.event(f"write refused: {exc}", level="block")
            return None

        decision = out.get("decision", out)
        t.kv("decision_id", decision.get("decision_id"))
        t.kv("Idempotency-Key", key)
        if out.get("idempotent_replay"):
            t.event("idempotent replay — the original row was returned, "
                    "nothing new was created", level="ok")
        else:
            t.event("recommendation recorded, awaiting adjuster confirmation",
                    level="ok")

        # A MORE_INFO outcome that names documents should ASK for them. This is
        # the second write and it is the one with a person on the other end, so
        # it is idempotent for a concrete reason: a retried pipeline must not
        # send the claimant two letters.
        for doc_type in result.verdict.requested_documents:
            if doc_type == "policy_identification":
                continue        # an internal data problem, not a claimant ask
            try:
                data.request_document(
                    result.claim_id, doc_type,
                    f"Required to assess this {result.triage.peril} claim. "
                    f"Requested by ClaimSense on behalf of the assigned adjuster.",
                    f"{key}-doc-{doc_type}")
                t.event(f"document request raised: {doc_type}", level="ok")
            except SystemError_ as exc:
                t.event(f"document request failed: {exc}", level="warn")

        return decision


def record_run(data: ClaimsData, result: RunResult) -> None:
    """One row per pipeline run, for the console's internals view.

    Latency is one of the engagement's quantified success criteria, so it is
    measured and stored rather than reconstructed from logs after the fact.
    """
    if data.mock:
        return
    import json
    import urllib.request

    # Written straight to Postgres rather than through a contract: agent_runs is
    # OUR telemetry, not a client system, and inventing a client-facing endpoint
    # for it would misrepresent where the table belongs.
    try:
        import psycopg  # noqa: F401
    except ImportError:
        return
    url = os.environ.get("CLAIMSENSE_DB_URL")
    if not url:
        return
    import psycopg
    with psycopg.connect(url) as conn:
        conn.execute(
            """INSERT INTO platform.agent_runs
                 (trace_id, claim_id, brain, outcome, source, duration_ms,
                  guardrails_fired, cited_clause_ids)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
            (result.trace_id, result.claim_id, result.brain,
             result.verdict.outcome, result.verdict.source,
             int(result.duration_ms), result.guardrails_fired,
             result.verdict.cited_clause_ids))
