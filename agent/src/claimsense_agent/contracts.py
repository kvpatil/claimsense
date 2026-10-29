"""The typed outputs every agent must produce.

M2 asks for STRICT typed outputs. These are dataclasses rather than Pydantic
models for one reason: the mock path has to run on the stdlib alone, and the
Agents SDK does accept a dataclass as `output_type=` just as happily as a
BaseModel — verified against openai-agents 0.24.0, which routes it through
pydantic's TypeAdapter, wraps it as {"response": {...}} and raises
ModelBehaviorError when the model's JSON does not fit. So the same type
annotates the mock reasoner and constrains the real model, and there is no
second definition to keep in step.

The vocabulary here is the contract between the pipeline, the database and the
console. `Outcome` matches cms.decisions.outcome; `VerdictSource` matches
cms.decisions.source. If one changes, all three change together.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

# The four decision outcomes. Every one is a RECOMMENDATION — a licensed
# adjuster confirms all four before anything is written back.
Outcome = Literal["APPROVE", "DENY", "MORE_INFO", "SIU_REFERRAL"]

# M2 requires a model-generated verdict to be distinguishable from a
# deterministic fallback. Making it a Literal on the type rather than a log line
# is what makes that distinction survive into the database and onto the screen.
VerdictSource = Literal["model", "deterministic_fallback"]

ClockStatus = Literal["BREACHED", "RED", "AMBER", "GREEN"]
CoverageFinding = Literal["covered", "excluded", "indeterminate"]
RiskBand = Literal["low", "elevated", "high"]


@dataclass
class DecisionBasis:
    """One input to the verdict, tagged by WHO decided it.

    This is the architecture figure made machine-readable. `kind="code"` means a
    deterministic function produced it and a model could not have changed it;
    `kind="judgment"` means a model produced it and `evidence` is what it relied
    on. The console renders the two in separate columns.
    """
    kind: Literal["code", "judgment"]
    name: str
    detail: str
    evidence: list[str] = field(default_factory=list)


@dataclass
class TriageDecision:
    """Stage 1 — what kind of claim is this, and what is the clock?"""
    claim_id: int
    peril: str
    product: str
    severity: Literal["low", "moderate", "high", "severe"]
    # The fair-claims clock. Dates are computed in code (determinism/clock.py);
    # the model states the classification, never the deadline.
    ack_due_at: str
    decision_due_at: str
    clock_status: ClockStatus
    hours_to_decision_deadline: float
    rationale: str
    confidence: float


@dataclass
class EvidenceBundle:
    """Stage 2 — what is on file, across which of the three systems."""
    claim_id: int
    source_systems: list[str]
    system_count: int
    # True when all three client systems answered. A claim the agent could only
    # see in one system is not a claim it should be adjudicating.
    sufficient: bool
    facts: list[str]
    documents_on_file: list[str]
    missing_documents: list[str]
    # Dropped by the input guardrail before reaching model context. Recorded so
    # the quarantine is auditable rather than silent.
    quarantined_document_ids: list[int] = field(default_factory=list)
    policy_resolved: bool = True


@dataclass
class CoverageOpinion:
    """Stage 3 — the money step. The only stage that may conclude on cover.

    `cited_clause_ids` must be a SUBSET of `retrieved_clause_ids`. The output
    guardrail enforces that, and a violation blocks the output rather than
    correcting it: a citation to a clause that was never retrieved is a
    fabrication, and silently dropping it would hide the fabrication.
    """
    claim_id: int
    finding: CoverageFinding
    statement: str
    cited_clause_ids: list[str]
    retrieved_clause_ids: list[str]
    confidence: float
    blocked: bool = False
    tripwire_reason: str | None = None


@dataclass
class RiskAssessment:
    """Stage 3b — fraud. The SCORE is arithmetic; the MEANING is judgment.

    `score` and `band` come from determinism/risk.py summing the weights
    recorded on cms.fraud_signals. `interpretation` is the model's reading of
    what those indicators amount to together, and it must name them.
    """
    claim_id: int
    score: int
    band: RiskBand
    indicators: list[str]
    interpretation: str
    refer_to_siu: bool


@dataclass
class Routing:
    """Which desk must handle the claim, and the desks it has crossed.

    Separate from the outcome on purpose. Routing answers WHO handles this;
    the coverage stages answer WHAT the answer is. They are independent — a
    claim can be a total loss (routes to appraisal) and excluded (denied
    regardless), and collapsing the two would lose that.
    """
    desk: str
    reason: str
    chain: list[str] = field(default_factory=list)
    escalated: bool = False
    # Present when the damage could be measured against a value at all.
    total_loss: bool = False
    damage_ratio: float | None = None


@dataclass
class ClaimVerdict:
    """Stage 4 — the first decision. A recommendation, never an action."""
    claim_id: int
    outcome: Outcome
    source: VerdictSource
    rationale: str
    cited_clause_ids: list[str]
    settlement_cents: int | None
    decision_basis: list[DecisionBasis]
    confidence: float
    blocked: bool = False
    blocked_reason: str | None = None
    # Named documents, when the outcome is MORE_INFO. "Send us more" is not an
    # actionable request; "send us the police report and a sworn proof of loss"
    # is, and it is what the DMS document-request write sends.
    requested_documents: list[str] = field(default_factory=list)
    # Structurally always True. It is a field rather than an assumption so the
    # write-back path has something to assert on, and so a future autonomous
    # mode has to change a value that someone can grep for.
    requires_human_confirmation: bool = True
    # Which desk must handle this next. Computed deterministically; a model
    # never chooses who works a claim.
    routing: Routing | None = None


@dataclass
class RunResult:
    """Everything one pipeline run produced, for the scorecard and the DB."""
    claim_id: int
    trace_id: str
    brain: str
    triage: TriageDecision
    evidence: EvidenceBundle
    coverage: CoverageOpinion
    risk: RiskAssessment
    verdict: ClaimVerdict
    duration_ms: float
    guardrails_fired: list[str] = field(default_factory=list)
    checks: list[tuple[str, bool, str]] = field(default_factory=list)
    # Which brain produced each judgment stage: "mock" | "model" | "fallback".
    # `brain` above is a summary for the scorecard; this is the per-stage
    # record it is derived from, and it is what lets a reviewer see that a run
    # labelled llm had its coverage opinion written by the mock reasoner.
    stage_brains: dict[str, str] = field(default_factory=dict)
