"""The live path, driven offline.

These tests exercise the REAL OpenAI Agents SDK — Runner, function_tool
dispatch, output_type validation, SQLiteSession — with a scripted model in
place of the provider's HTTP reply. That is the only way the claim "the agent
set is implemented on the Agents SDK with strict typed outputs" gets checked
on a commit rather than only by whoever holds Bedrock credentials.

Skipped wholesale when openai-agents is not installed, because the $0 gate
must keep passing on the stdlib alone.
"""
from __future__ import annotations

import asyncio
import json

import os

import pytest

# A skipped test looks exactly like a passing one, so CI sets
# CLAIMSENSE_REQUIRE_SDK=1 and a missing SDK becomes a failure there. Locally,
# `make verify` on a stdlib-only venv still skips cleanly.
if os.environ.get("CLAIMSENSE_REQUIRE_SDK") in ("1", "true", "yes"):
    import agents  # noqa: F401  — must be importable; let the ImportError fly
else:
    pytest.importorskip("agents", reason="live-path extra not installed; "
                                         "set CLAIMSENSE_REQUIRE_SDK=1 to "
                                         "require it")

from agents.items import ModelResponse                      # noqa: E402
from agents.models.interface import Model                    # noqa: E402
from agents.usage import Usage                               # noqa: E402

from claimsense_agent.brain import BrainConfig               # noqa: E402
from claimsense_agent.contracts import (CoverageOpinion,     # noqa: E402
                                        EvidenceBundle, TriageDecision)
from claimsense_agent.systems import ClaimsData              # noqa: E402
from claimsense_agent.trace import Tracer                    # noqa: E402
from fake_model import _call, _text                          # noqa: E402

CFG = BrainConfig(mode="llm", provider="fake", fast="fake/fast",
                  smart="fake/smart")

# What each stage's model is scripted to do: call its tool, then return a
# structured output. Deliberately WRONG on every field the model is not
# allowed to decide, so the reconcile step has something to catch.
SCRIPT = {
    "TriageDecision": (
        _call("load_claim"),
        {"claim_id": 1, "peril": "fire", "product": "HO3",
         "severity": "severe", "ack_due_at": "1999-01-01",
         "decision_due_at": "1999-01-02", "clock_status": "BREACHED",
         "hours_to_decision_deadline": -999.0,
         "rationale": "the model's reading of the file", "confidence": 0.91}),
    "EvidenceBundle": (
        _call("gather_evidence"),
        {"claim_id": 1, "source_systems": ["invented"], "system_count": 1,
         "sufficient": False, "facts": ["the model's own summary"],
         "documents_on_file": ["invented"], "missing_documents": ["invented"],
         "quarantined_document_ids": [999], "policy_resolved": False}),
    "CoverageOpinion": (
        _call("search_policy_clauses", {"query": "fire damage dwelling"}),
        {"claim_id": 1, "finding": "covered",
         "statement": "Covered under the dwelling grant [HO3-I-A-1].",
         "cited_clause_ids": ["HO3-I-A-1"],
         "retrieved_clause_ids": ["TOTALLY-MADE-UP"], "confidence": 0.88,
         "blocked": True, "tripwire_reason": "the model grading itself"}),
}


class ScriptedStageModel(Model):
    """Replies based on which output_type it was handed.

    Keyed on the schema rather than on construction order, so it does not
    care which agent the factory builds first.
    """

    def __init__(self):
        self.turns: dict[str, int] = {}
        self.schemas_seen: list[str] = []
        self.tools_seen: dict[str, list[str]] = {}

    def _respond(self, tools, output_schema) -> ModelResponse:
        name = output_schema.name() if output_schema else "none"
        self.schemas_seen.append(name)
        self.tools_seen[name] = [getattr(t, "name", "?") for t in tools]
        tool_call, payload = SCRIPT[name]
        n = self.turns.get(name, 0)
        self.turns[name] = n + 1
        out = [tool_call] if n == 0 else [_text({"response": payload})]
        return ModelResponse(output=out, usage=Usage(), response_id="resp_fake")

    async def get_response(self, system_instructions, input, model_settings,
                           tools, output_schema, handoffs, tracing, *,
                           previous_response_id=None, conversation_id=None,
                           prompt=None):
        return self._respond(tools, output_schema)

    async def stream_response(self, system_instructions, input, model_settings,
                              tools, output_schema, handoffs, tracing, *,
                              previous_response_id=None, conversation_id=None,
                              prompt=None):
        from openai.types.responses import Response, ResponseCompletedEvent
        resp = self._respond(tools, output_schema)
        yield ResponseCompletedEvent(
            type="response.completed", sequence_number=0,
            response=Response(id="resp_fake", created_at=0.0, model="fake",
                              object="response", output=resp.output,
                              parallel_tool_calls=False, tool_choice="auto",
                              tools=[]))


def _run(claim_id=4401, factory=None):
    from claimsense_agent.agents.sdk_runtime import run_live_stages
    data = ClaimsData(mock=True)
    state: dict = {}
    model = ScriptedStageModel()
    sr = asyncio.run(run_live_stages(
        data, claim_id, cfg=CFG, tracer=Tracer(quiet=True), state=state,
        governing_limit_cents=45_000_000,
        model_factory=factory or (lambda _name: model)))
    return sr, state, model


# --- the SDK really ran -----------------------------------------------------

def test_all_three_stages_ran_on_the_sdk():
    sr, _, model = _run()
    assert sr.brains == {"triage": "model", "evidence": "model",
                         "coverage": "model"}
    assert sr.all_model and not sr.fell_back()
    # One schema per stage, seen twice each: the tool turn and the output turn.
    assert sorted(set(model.schemas_seen)) == [
        "CoverageOpinion", "EvidenceBundle", "TriageDecision"]


def test_each_agent_got_only_its_own_tool():
    _, _, model = _run()
    assert model.tools_seen["TriageDecision"] == ["load_claim"]
    assert model.tools_seen["EvidenceBundle"] == ["gather_evidence"]
    assert model.tools_seen["CoverageOpinion"] == ["search_policy_clauses"]


def test_outputs_are_the_typed_contracts():
    sr, _, _ = _run()
    assert isinstance(sr.triage, TriageDecision)
    assert isinstance(sr.evidence, EvidenceBundle)
    assert isinstance(sr.coverage, CoverageOpinion)


def test_the_tools_actually_reached_the_client_systems():
    _, state, _ = _run()
    assert state["bundle"]["claim"]["claim_id"]           # load_claim ran
    assert isinstance(state["evidence"], EvidenceBundle)  # gather_evidence ran
    assert state["retrieved"]                             # search ran


# --- reconcile: the model keeps its judgment and nothing else ---------------

def test_model_keeps_its_judgment():
    sr, _, _ = _run()
    assert sr.triage.severity == "severe"                  # its call, kept
    assert sr.triage.rationale == "the model's reading of the file"
    assert sr.triage.confidence == 0.91
    assert sr.coverage.finding == "covered"
    assert sr.coverage.cited_clause_ids == ["HO3-I-A-1"]
    assert sr.evidence.facts == ["the model's own summary"]


def test_clock_dates_come_from_code_not_the_model():
    sr, state, _ = _run()
    ck = state["clock_facts"]
    assert sr.triage.clock_status == ck["clock_status"] != "BREACHED"
    assert sr.triage.decision_due_at == ck["decision_due_at"]
    assert sr.triage.hours_to_decision_deadline != -999.0
    assert sr.triage.claim_id == 4401


def test_the_systems_inventory_comes_from_the_tool_not_the_model():
    sr, state, _ = _run()
    truth = state["evidence"]
    assert sr.evidence.source_systems == truth.source_systems != ["invented"]
    assert sr.evidence.system_count == truth.system_count == 3
    assert sr.evidence.sufficient is True
    assert sr.evidence.quarantined_document_ids == truth.quarantined_document_ids
    assert 999 not in sr.evidence.quarantined_document_ids


def test_a_model_cannot_widen_its_own_citation_allowlist():
    """The security property. retrieved_clause_ids is what the tripwire
    checks citations against; if the model could set it, it could cite
    anything and the guardrail would wave it through."""
    sr, state, _ = _run()
    assert "TOTALLY-MADE-UP" not in sr.coverage.retrieved_clause_ids
    assert sr.coverage.retrieved_clause_ids == state["retrieved"]
    assert set(sr.coverage.cited_clause_ids) <= set(sr.coverage.retrieved_clause_ids)


def test_a_model_cannot_clear_its_own_guardrail():
    sr, _, _ = _run()
    assert sr.coverage.blocked is False       # the tripwire has not run yet
    assert sr.coverage.tripwire_reason is None


# --- failure handling -------------------------------------------------------

class _Broken(Model):
    """Returns output that does not fit the dataclass."""

    def __init__(self):
        self.attempts = 0

    def _resp(self):
        self.attempts += 1
        return ModelResponse(output=[_text({"response": {"nope": True}})],
                             usage=Usage(), response_id="r")

    async def get_response(self, *a, **k):
        return self._resp()

    async def stream_response(self, *a, **k):
        from openai.types.responses import Response, ResponseCompletedEvent
        r = self._resp()
        yield ResponseCompletedEvent(
            type="response.completed", sequence_number=0,
            response=Response(id="r", created_at=0.0, model="fake",
                              object="response", output=r.output,
                              parallel_tool_calls=False, tool_choice="auto",
                              tools=[]))


def test_malformed_output_falls_back_and_is_recorded():
    broken = _Broken()
    sr, _, _ = _run(factory=lambda _n: broken)
    assert sr.brains == {"triage": "fallback", "evidence": "fallback",
                         "coverage": "fallback"}
    assert not sr.all_model
    assert sorted(sr.fell_back()) == ["coverage", "evidence", "triage"]
    # Still produced usable typed results — the run does not die.
    assert isinstance(sr.triage, TriageDecision)
    assert isinstance(sr.coverage, CoverageOpinion)


def test_malformed_output_is_retried_exactly_once_per_stage():
    """A ModelBehaviorError is worth one more sample. It is not worth six."""
    broken = _Broken()
    _run(factory=lambda _n: broken)
    assert broken.attempts == 6        # three stages x two attempts


def test_auth_failure_is_not_retried():
    """Retrying a bad credential is latency with no chance of success."""
    from claimsense_agent.agents.sdk_runtime import _is_retryable
    from litellm import exceptions as le
    from agents.exceptions import ModelBehaviorError

    nope = le.AuthenticationError(message="bad key", llm_provider="bedrock",
                                  model="m")
    assert _is_retryable(nope) is False
    assert _is_retryable(ModelBehaviorError("bad json")) is True
    assert _is_retryable(le.RateLimitError(message="slow down",
                                           llm_provider="bedrock",
                                           model="m")) is True
