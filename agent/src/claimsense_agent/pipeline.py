"""The pipeline — one claim, end to end.

    load (CMS+PAS+DMS) → deterministic facts → Triage ➜ Evidence ➜ Coverage
    (+guardrails) ➜ Risk ➜ Adjudicate → override check → scorecard

The order is deliberate and is the architecture figure in execution order: the
deterministic facts are established BEFORE any stage reasons, so every agent is
handed dates and money as given rather than asked to work them out. The
guardrails sit on either side of the stage that moves money.

Nothing here writes to a client system. The pipeline produces a RECOMMENDATION;
the write-back happens when a licensed adjuster confirms it, which is a
different code path with a different authorisation check.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .brain import BrainConfig
from .agents import adjudicator as adjudicator_agent
from .agents import coverage as coverage_agent
from .agents import evidence as evidence_agent
from .agents import risk as risk_agent
from .agents import triage as triage_agent
from .contracts import DecisionBasis, Routing, RunResult
from .determinism import authority, clock, eligibility, identity, money, risk
from .guardrails import citation_tripwire, determinism_override, scan_for_pii
from .retrieval import Retriever
from .systems import ClaimsData, claim_bundle
from .trace import (BOLD, CYAN, DIM, GREEN, GREY, MAGENTA, RED, RESET, YELLOW,
                    Tracer, blocked, okline, warnline)


def run_pipeline(data: ClaimsData, claim_id: int | str, *, tracer: Tracer,
                 brain: "BrainConfig | str" = "mock",
                 now: datetime | None = None,
                 tripwire_demo: bool = False) -> RunResult:
    """Work one claim end to end.

    `brain` accepts either a BrainConfig — in which case a non-mock config
    routes the three judgment stages through the OpenAI Agents SDK — or a
    bare string, which is the mock path with that string as its label. The
    string form is what the eval gate and the tests use: $0, no network, and
    the SDK packages never imported.
    """
    # The fixture pins its own "now" so evals cannot start failing on a
    # calendar. The live path has no such anchor and uses the real clock.
    if now is None and data.mock and data.reference_now:
        now = datetime.fromisoformat(data.reference_now)
    now = now or datetime.now(timezone.utc)

    basis: list[DecisionBasis] = []
    guardrails_fired: list[str] = []

    # ---- load across the three client systems ------------------------------
    with tracer.span("load_claim_bundle", kind="tool") as t:
        bundle = claim_bundle(data, claim_id)
        claim = bundle["claim"]
        policy = bundle.get("policy")
        t.event(f"read claims_management (backend: {data.backend})", level="tool")
        t.event("read policy_administration" if policy else
                "policy_administration returned NO RECORD", level="tool" if policy else "warn")
        t.event(f"read document_store — {len(bundle['documents'])} document(s)", level="tool")
        t.kv("claim", f"{claim['claim_number']}  {claim['peril']}  "
                      f"{money.usd(claim['claimed_amount_cents'])}")
        t.kv("date of loss", claim["date_of_loss"])

    # ---- deterministic facts, established BEFORE anything reasons ----------
    with tracer.span("deterministic: eligibility · money · risk · access",
                     kind="code") as t:
        elig = eligibility.check(policy, claim["date_of_loss"], claim["reported_at"])
        t.kv("policy resolved", "yes" if elig.policy_resolved else f"{RED}NO{RESET}")
        t.kv("in force at loss", "yes" if elig.in_force else f"{RED}NO{RESET}")
        for r in elig.reasons:
            t.event(r, level="warn")
        basis.append(DecisionBasis(
            kind="code", name="eligibility",
            detail=("cover in force on the date of loss" if elig.in_force
                    else "; ".join(elig.reasons)),
            evidence=[f"policy={claim['policy_id']}", f"dol={claim['date_of_loss']}"]))

        product = policy["product"] if policy else "unknown"
        cov = money.governing_coverage(product, claim["peril"], bundle["coverages"])
        settlement = None
        if cov:
            settlement = money.settle(
                claim["claimed_amount_cents"], cov["limit_cents"],
                cov["deductible_cents"], cov["coinsurance_pct"])
            t.kv("governing coverage", f"{cov['coverage_code']}  limit "
                                       f"{money.usd(cov['limit_cents'])}  "
                                       f"deductible {money.usd(cov['deductible_cents'])}")
            t.event(settlement.explain(), level="info")
            basis.append(DecisionBasis(
                kind="code", name="settlement arithmetic",
                detail=settlement.explain(),
                evidence=[f"coverage={cov['coverage_code']}"]))
        else:
            t.kv("governing coverage", f"{YELLOW}none on this form{RESET}")

        scored = risk.score(bundle["signals"])
        t.kv("fraud score", f"{scored.score} ({scored.band})"
                            + (f"  {RED}→ SIU threshold crossed{RESET}"
                               if scored.refer_to_siu else ""))
        basis.append(DecisionBasis(
            kind="code", name="fraud score",
            detail=f"{scored.score} ({scored.band}); referral threshold "
                   f"{risk.REFER_AT}",
            evidence=scored.detail))

        ck = clock.compute(claim["reported_at"], claim.get("loss_state", ""), now)
        basis.append(DecisionBasis(
            kind="code", name="fair-claims clock",
            detail=f"decision due {ck.decision_due_at.date()} ({ck.status})",
            evidence=[f"reported={claim['reported_at'][:10]}"]))

        adjuster = bundle.get("adjuster")
        access = identity.can_view(adjuster, claim, siu_referred=scored.refer_to_siu)
        t.kv("access", f"{adjuster['full_name']} ({adjuster['role']}) — "
                       f"{access.reason}" if adjuster else "unassigned")

        # Is the item written off rather than repaired? Arithmetic against the
        # actual cash value — and it changes which DESK handles the claim, not
        # what the coverage answer is.
        tl = authority.total_loss(claim["claimed_amount_cents"],
                                  claim.get("acv_cents"),
                                  claim.get("loss_state", ""))
        if tl.applicable:
            t.kv("total loss", (f"{RED}YES{RESET} — " if tl.is_total_loss else "no — ")
                               + tl.reason)
            basis.append(DecisionBasis(
                kind="code", name="total-loss test", detail=tl.reason,
                evidence=[f"acv={money.usd(claim.get('acv_cents'))}"]))

    # ---- who reasons -------------------------------------------------------
    # The ONLY branch in this function. Everything downstream of it — the
    # guardrails, the risk interpretation, the adjudication, the override, the
    # routing, the checks and the scorecard — runs identically whichever brain
    # produced the three stage outputs. That invariant is the architectural
    # claim; it is worth it being literally true rather than approximately so.
    cfg = None if isinstance(brain, str) else brain
    stage_brains: dict[str, str] = {}
    triage = ev = cvg = None
    retriever: Retriever | None = None

    if cfg is not None and not cfg.is_mock:
        import asyncio

        from .agents.sdk_runtime import run_live_stages
        sdk_state: dict[str, Any] = {}
        sr = asyncio.run(run_live_stages(
            data, claim_id, cfg=cfg, tracer=tracer, state=sdk_state, now=now,
            governing_limit_cents=cov["limit_cents"] if cov else None))
        triage, ev, cvg = sr.triage, sr.evidence, sr.coverage
        stage_brains = dict(sr.brains)
        # Reuse the retriever the agents searched through, so the trace below
        # resolves clause titles from the same corpus the citations came from.
        retriever = sdk_state.get("retriever")

    # ---- 1. TRIAGE ---------------------------------------------------------
    with tracer.span("triage_agent.classify", kind="agent") as t:
        if triage is None:
            triage = triage_agent.run(
                bundle, now=now,
                governing_limit_cents=cov["limit_cents"] if cov else None)
            stage_brains["triage"] = "mock"
        t.kv("peril / product", f"{triage.peril} on {triage.product}")
        t.kv("severity", triage.severity)
        col = {"BREACHED": RED, "RED": RED, "AMBER": YELLOW, "GREEN": GREEN}[triage.clock_status]
        t.kv("decision clock", f"{col}{triage.clock_status}{RESET} "
                               f"({triage.hours_to_decision_deadline / 24:.0f}d)")
        t.event(triage.rationale)
        basis.append(DecisionBasis(kind="judgment", name="triage",
                                   detail=triage.rationale,
                                   evidence=[f"fnol:{claim['claim_number']}"]))

    with tracer.span("handoff: Triage ➜ Evidence", kind="handoff") as t:
        t.event("control transferred", level="info")

    # ---- 2. EVIDENCE (input guardrail fires here) --------------------------
    with tracer.span("evidence_agent.gather", kind="agent") as t:
        if ev is None:
            ev = evidence_agent.run(bundle)
            stage_brains["evidence"] = "mock"
        for s in ev.source_systems:
            t.event(f"read {s}", level="tool")
        t.kv("systems answered", f"{ev.system_count}/3 "
                                 + (f"{GREEN}sufficient{RESET}" if ev.sufficient
                                    else f"{RED}INSUFFICIENT{RESET}"))

        with tracer.span("input_guardrail: quarantine_poisoned", kind="guardrail") as g:
            if ev.quarantined_document_ids:
                guardrails_fired.append("quarantine_poisoned")
                for did in ev.quarantined_document_ids:
                    blocked(f"QUARANTINED document {did} — injected instruction "
                            f"NOT ingested into model context")
                g.kv("quarantined", ev.quarantined_document_ids)
            else:
                g.event("no poisoned documents in this file", level="ok")

        if ev.missing_documents:
            t.kv("missing", f"{YELLOW}{', '.join(ev.missing_documents)}{RESET}")
        for f in ev.facts[:6]:
            t.event(f"{DIM}{f[:120]}{RESET}")
        basis.append(DecisionBasis(
            kind="judgment", name="evidence",
            detail=f"{ev.system_count} of 3 systems answered; "
                   f"missing: {', '.join(ev.missing_documents) or 'nothing'}",
            evidence=ev.documents_on_file))

    with tracer.span("handoff: Evidence ➜ Coverage", kind="handoff") as t:
        t.event(f"control transferred — the money step", level="info")

    # ---- 3. COVERAGE (retrieval + output guardrail) ------------------------
    with tracer.span("coverage_agent.decide", kind="agent") as t:
        retriever = retriever or Retriever(data.get_clauses())
        if cvg is None:
            cvg = coverage_agent.run(bundle, retriever,
                                     force_uncited=tripwire_demo)
            stage_brains["coverage"] = "mock"
        elif tripwire_demo:
            # --tripwire must demonstrate the guardrail on BOTH brains. A
            # model cannot be reliably instructed to misbehave on cue, so the
            # citations are stripped here instead — the tripwire then sees
            # exactly what it would see from a model that cited nothing.
            cvg.cited_clause_ids = []

        with tracer.span("retrieval: BM25 over the clause corpus", kind="retrieval") as r:
            r.kv("retrieved", f"{len(cvg.retrieved_clause_ids)} clause(s)")
            for cid in cvg.retrieved_clause_ids[:5]:
                cl = retriever.by_id(cid)
                r.event(f"{GREY}{cid:<16}{RESET} {cl['title']}" if cl else cid)

        t.kv("finding", f"{BOLD}{cvg.finding}{RESET}")
        t.event(cvg.statement)

        with tracer.span("output_guardrail: citation_tripwire", kind="guardrail") as g:
            tw = citation_tripwire(cvg.statement, cvg.cited_clause_ids,
                                   cvg.retrieved_clause_ids)
            if tw.triggered:
                guardrails_fired.append("citation_tripwire")
                cvg.blocked = True
                cvg.tripwire_reason = tw.reason
                g.event(tw.reason, level="block")
                blocked("OUTPUT BLOCKED — not returned, not written back")
                okline("routed to a licensed adjuster instead")
            elif tw.makes_money_claim:
                g.event(f"coverage conclusion grounded in "
                        f"{cvg.cited_clause_ids}", level="cite")
            else:
                g.event("no money-moving claim to gate", level="ok")

        basis.append(DecisionBasis(
            kind="judgment", name="coverage",
            detail=cvg.statement,
            evidence=cvg.cited_clause_ids or ["<none — blocked>"]))

    # ---- 3b. RISK ----------------------------------------------------------
    with tracer.span("risk_agent.interpret", kind="agent") as t:
        rsk = risk_agent.run(int(claim["claim_id"]), scored)
        t.kv("band", f"{rsk.band} (score {rsk.score})")
        t.event(rsk.interpretation)
        basis.append(DecisionBasis(kind="judgment", name="risk",
                                   detail=rsk.interpretation,
                                   evidence=rsk.indicators))

    # ---- 4. ADJUDICATE -----------------------------------------------------
    with tracer.span("adjudicator.decide", kind="agent") as t:
        verdict = adjudicator_agent.run(
            triage=triage, evidence=ev, coverage=cvg, risk=rsk,
            eligibility=elig, settlement=settlement, basis=basis,
            fell_back=[k for k, v in stage_brains.items() if v == "fallback"])

        # A blocked coverage opinion cannot support an outcome that rests on
        # it. Fail closed: the claim goes to a human rather than proceeding on
        # a conclusion the guardrail just refused to return.
        if cvg.blocked:
            verdict.outcome = "MORE_INFO"
            verdict.blocked = True
            verdict.blocked_reason = cvg.tripwire_reason
            verdict.settlement_cents = None
            verdict.cited_clause_ids = []
            verdict.rationale = (
                "The coverage opinion was blocked by the citation guardrail "
                f"({cvg.tripwire_reason}). No coverage conclusion is being "
                "returned. A licensed adjuster must read the file and decide.")

        # ---- the override check: arithmetic beats eloquence ----------------
        with tracer.span("output_guardrail: determinism_override", kind="guardrail") as g:
            ovr = determinism_override(verdict.outcome, elig, settlement)
            if ovr.overridden:
                guardrails_fired.append("determinism_override")
                g.event(ovr.reason, level="block")
                g.event(f"outcome {verdict.outcome} → {ovr.outcome}; "
                        f"source re-stamped deterministic_fallback", level="block")
                verdict.outcome = ovr.outcome
                verdict.source = "deterministic_fallback"
                verdict.rationale = f"{ovr.reason}. " + verdict.rationale
                verdict.settlement_cents = None
            else:
                g.event("model verdict consistent with the deterministic checks",
                        level="ok")

        with tracer.span("output_guardrail: pii_scan", kind="guardrail") as g:
            pii = scan_for_pii(verdict.rationale)
            if pii:
                guardrails_fired.append("pii_scan")
                g.event(f"synthetic-only invariant violated: {pii}", level="block")
                verdict.blocked = True
            else:
                g.event("no personal data in the drafted output", level="ok")

        # ---- routing: WHO handles this, decided by numbers ----------------
        with tracer.span("deterministic: settlement authority · routing",
                         kind="code") as g:
            r = authority.route(adjuster=adjuster, outcome=verdict.outcome,
                                settlement_cents=verdict.settlement_cents,
                                tl=tl, refer_to_siu=scored.refer_to_siu)
            verdict.routing = Routing(
                desk=r.desk, reason=r.reason, chain=r.chain,
                escalated=r.escalated, total_loss=tl.is_total_loss,
                damage_ratio=round(tl.ratio, 3) if tl.ratio is not None else None)
            g.kv("desk", f"{BOLD}{r.desk}{RESET}"
                         + (f"  {YELLOW}escalated{RESET}" if r.escalated else ""))
            g.kv("path", " → ".join(r.chain))
            g.event(r.reason)
            basis.append(DecisionBasis(
                kind="code", name="routing", detail=r.reason,
                evidence=r.chain))

        src_col = GREEN if verdict.source == "model" else MAGENTA
        t.kv("OUTCOME", f"{BOLD}{verdict.outcome}{RESET}")
        t.kv("source", f"{src_col}{verdict.source}{RESET}")
        t.kv("settlement", money.usd(verdict.settlement_cents))
        t.kv("citations", verdict.cited_clause_ids or "—")
        t.kv("desk", verdict.routing.desk if verdict.routing else "—")

    result = RunResult(
        claim_id=int(claim["claim_id"]), trace_id=tracer.trace_id,
        brain=_brain_label(brain, stage_brains),
        triage=triage, evidence=ev, coverage=cvg, risk=rsk, verdict=verdict,
        duration_ms=tracer.total_ms(), guardrails_fired=guardrails_fired,
        stage_brains=stage_brains,
    )
    result.checks = _build_checks(result, elig, settlement)
    return result


def _brain_label(brain: BrainConfig | str, stage_brains: dict[str, str]) -> str:
    """What actually reasoned — not what was configured.

    This used to be `cfg.mode`, which meant a --live run with credentials
    present printed `brain=llm` over numbers the mock reasoners had produced.
    A run that succeeds while misreporting its own provenance is worse than
    one that fails, so the label is derived from the stage record instead.
    """
    if isinstance(brain, str):
        return brain
    if brain.is_mock:
        return "mock"
    fell = [k for k, v in stage_brains.items() if v != "model"]
    if not fell:
        return "llm"
    if len(fell) == len(stage_brains):
        return "mock (every stage fell back)"
    return f"llm (partial: {', '.join(fell)} fell back)"


def _build_checks(r: RunResult, elig, settlement) -> list[tuple[str, bool, str]]:
    v, c, e = r.verdict, r.coverage, r.evidence
    citation_ok = (not c.cited_clause_ids
                   or set(c.cited_clause_ids) <= set(c.retrieved_clause_ids))
    return [
        ("one of the four outcomes produced", v.outcome in
         ("APPROVE", "DENY", "MORE_INFO", "SIU_REFERRAL"), v.outcome),
        ("all three client systems read", e.sufficient,
         f"{e.system_count}/3 answered"),
        ("every citation was actually retrieved", citation_ok,
         f"cited {c.cited_clause_ids or '—'}"),
        ("poisoned documents quarantined",
         not e.quarantined_document_ids or "quarantine_poisoned" in r.guardrails_fired,
         f"ids {e.quarantined_document_ids}" if e.quarantined_document_ids else "none present"),
        ("money-moving output is grounded", not c.blocked,
         c.tripwire_reason or "grounded"),
        ("verdict source is explicit", v.source in ("model", "deterministic_fallback"),
         v.source),
        ("settlement only on APPROVE",
         (v.settlement_cents is None) == (v.outcome != "APPROVE"),
         money.usd(v.settlement_cents)),
        ("human confirmation required", v.requires_human_confirmation, "always"),
        ("every judgment stage recorded its brain",
         set(r.stage_brains) == {"triage", "evidence", "coverage"},
         # Compact on purpose — the scorecard truncates the note column, and
         # "model, fallback" is the fact that matters. stage_brains carries
         # the per-stage detail for anything that needs it.
         ", ".join(sorted(set(r.stage_brains.values()))) or "none"),
        ("routed to a named desk", bool(v.routing and v.routing.desk),
         v.routing.desk if v.routing else "—"),
        ("settlement within the desk's authority",
         not (v.outcome == "APPROVE" and v.routing and v.routing.escalated
              and v.routing.desk not in ("appraiser", "siu"))
         or bool(v.routing and v.routing.escalated),
         "escalated" if v.routing and v.routing.escalated else "in authority"),
    ]


def print_scorecard(r: RunResult, tracer: Tracer) -> None:
    bar = "─" * 70
    print(f"\n{BOLD}{CYAN}┌{bar}┐{RESET}")
    # Build the title first, then pad to the bar. Computing the padding inline
    # from a literal width is how box borders drift: the arithmetic has to be
    # re-derived every time the title text changes, and it silently will not be.
    title = f"SCORECARD — claim {r.claim_id}"
    print(f"{BOLD}{CYAN}│{RESET} {BOLD}{title}{' ' * (len(bar) - len(title) - 1)}"
          f"{RESET}{BOLD}{CYAN}│{RESET}")
    print(f"{BOLD}{CYAN}├{bar}┤{RESET}")
    for name, ok, note in r.checks:
        mark = f"{GREEN}PASS{RESET}" if ok else f"{RED}FAIL{RESET}"
        print(f"{CYAN}│{RESET} [{mark}] {name:<42} {GREY}{note[:22]}{RESET}")
    print(f"{BOLD}{CYAN}├{bar}┤{RESET}")
    src = (f"{GREEN}model{RESET}" if r.verdict.source == "model"
           else f"{MAGENTA}deterministic fallback{RESET}")
    print(f"{CYAN}│{RESET} outcome: {BOLD}{r.verdict.outcome}{RESET}   "
          f"source: {src}   confidence: {r.verdict.confidence:.2f}")
    if r.guardrails_fired:
        print(f"{CYAN}│{RESET} guardrails fired: {YELLOW}{', '.join(r.guardrails_fired)}{RESET}")
    print(f"{BOLD}{CYAN}└{bar}┘{RESET}")
    print(f"{GREY}brain={r.brain}  {r.duration_ms:.1f} ms  trace_id={r.trace_id}{RESET}")
    warnline("RECOMMENDATION ONLY — a licensed adjuster confirms every outcome")
