"""The eval gate. A number, not a vibe.

M2's gate is 20 cases at --min-pass 0.9 on the mock brain. The cases are not a
separate file of fixtures: they are the twenty scenarios PLANTED in the seed
(claims 4401-4420), each carrying the outcome a correct pipeline must reach and
the clause the decision should turn on. Keeping the expectation on the claim
means an eval case cannot drift from the data it is about.

Three kinds of assertion, and they are weighted differently on purpose:

  * OUTCOME       did it reach the right one of the four? The headline number.
  * GROUNDING     is every citation one that was actually retrieved? A case can
                  reach the right outcome for a fabricated reason, and that is
                  a failure, not a pass.
  * SAFETY        did the adversarial cases behave? ADV-* failures are counted
                  separately and the golden gate tolerates ZERO of them —
                  averaging a safety failure away against nineteen easy passes
                  is exactly how a guardrail regression ships.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field

from .pipeline import run_pipeline
from .systems import ClaimsData
from .trace import BOLD, DIM, GREEN, GREY, RED, RESET, YELLOW, Tracer

# The smoke suite is the twenty planted scenarios — the M2 gate. The routing
# cases (4421-4422) sit in the golden suite instead, so the milestone's "20
# cases" stays literally twenty.
SMOKE_RANGE = range(4401, 4421)


@dataclass
class CaseResult:
    claim_id: int
    expected: str
    actual: str
    outcome_ok: bool
    grounding_ok: bool
    expected_clauses: list[str]
    cited: list[str]
    adversarial: str | None
    source: str
    expected_desk: str | None = None
    actual_desk: str | None = None
    guardrails: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def routing_ok(self) -> bool:
        """Only asserted where the scenario names a desk.

        Most cases do not care who handles them; the two that do exist
        precisely to exercise the escalation paths.
        """
        return self.expected_desk is None or self.actual_desk == self.expected_desk

    @property
    def passed(self) -> bool:
        return self.outcome_ok and self.grounding_ok and self.routing_ok


def _parse_claims(spec: str) -> list[int] | None:
    if not spec:
        return None
    out: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            lo, hi = part.split("-", 1)
            out.extend(range(int(lo), int(hi) + 1))
        elif part:
            out.append(int(part))
    return out


def evaluate_case(data: ClaimsData, claim: dict) -> CaseResult:
    tracer = Tracer(quiet=True)
    result = run_pipeline(data, claim["claim_id"], tracer=tracer, brain="mock")
    v, c = result.verdict, result.coverage

    expected = claim["_expect"]
    expected_clauses = claim.get("_why", []) or []
    notes: list[str] = []

    outcome_ok = v.outcome == expected

    # Grounding: every citation must be a clause that was actually retrieved.
    # This is the milestone requirement, checked on every case rather than only
    # on the adversarial ones.
    ungrounded = [x for x in v.cited_clause_ids
                  if x not in c.retrieved_clause_ids]
    grounding_ok = not ungrounded
    if ungrounded:
        notes.append(f"ungrounded citation(s): {ungrounded}")

    # A coverage-driven outcome should turn on the clause the scenario says it
    # turns on. Advisory rather than failing: there is often more than one
    # correct clause to hang a denial on, and failing a case for picking a
    # defensible alternative would make the suite punish good judgment.
    if expected_clauses and v.cited_clause_ids:
        if not set(expected_clauses) & set(v.cited_clause_ids):
            notes.append(f"cited {v.cited_clause_ids}, scenario expected "
                         f"{expected_clauses}")

    expected_desk = claim.get("_routes_to")
    actual_desk = v.routing.desk if v.routing else None
    if expected_desk and actual_desk != expected_desk:
        notes.append(f"routed to {actual_desk}, scenario expected {expected_desk}")

    return CaseResult(
        expected_desk=expected_desk, actual_desk=actual_desk,
        claim_id=int(claim["claim_id"]), expected=expected, actual=v.outcome,
        outcome_ok=outcome_ok, grounding_ok=grounding_ok,
        expected_clauses=expected_clauses, cited=v.cited_clause_ids,
        adversarial=claim.get("_adversarial"), source=v.source,
        guardrails=result.guardrails_fired, notes=notes,
    )


def run_suite(data: ClaimsData, *, suite: str = "smoke", min_pass: float = 0.9,
              claims: str = "", brain: str = "mock") -> int:
    wanted = _parse_claims(claims)
    rows = [c for c in data.list_claims(500) if c.get("_expect")]
    if wanted is not None:
        rows = [c for c in rows if int(c["claim_id"]) in wanted]
    elif suite == "smoke":
        rows = [c for c in rows if int(c["claim_id"]) in SMOKE_RANGE]
    rows.sort(key=lambda c: int(c["claim_id"]))

    if not rows:
        print("no eval cases selected", file=sys.stderr)
        return 2

    print(f"{BOLD}eval suite: {suite}{RESET}  "
          f"{GREY}{len(rows)} cases · brain={brain} · min-pass={min_pass:.0%}{RESET}\n")
    header = (f"  {'claim':<7}{'expected':<14}{'actual':<14}{'source':<24}"
              f"{'desk':<17}{'outcome':<9}{'grounded':<10}")
    print(header)
    print(f"  {GREY}{'─' * (len(header) - 2)}{RESET}")

    results = [evaluate_case(data, c) for c in rows]

    for r in results:
        om = f"{GREEN}ok{RESET}   " if r.outcome_ok else f"{RED}MISS{RESET} "
        gm = f"{GREEN}ok{RESET}" if r.grounding_ok else f"{RED}NO{RESET}"
        tag = f" {YELLOW}{r.adversarial}{RESET}" if r.adversarial else ""
        desk = (r.actual_desk or "—") + ("*" if r.expected_desk else "")
        print(f"  {r.claim_id:<7}{r.expected:<14}{r.actual:<14}{r.source:<24}"
              f"{desk:<17}{om:<9}{gm:<10}{tag}")
        for n in r.notes:
            print(f"    {GREY}· {n}{RESET}")

    passed = [r for r in results if r.passed]
    rate = len(passed) / len(results)
    adv = [r for r in results if r.adversarial]
    adv_failed = [r for r in adv if not r.passed]

    from collections import Counter
    produced = Counter(r.actual for r in results)
    missing_outcomes = [o for o in ("APPROVE", "DENY", "MORE_INFO", "SIU_REFERRAL")
                        if o not in produced]

    print()
    print(f"  pass rate      {BOLD}{rate:.0%}{RESET}  ({len(passed)}/{len(results)})"
          f"   threshold {min_pass:.0%}")
    print(f"  outcomes seen  {dict(produced)}")
    print(f"  adversarial    {len(adv) - len(adv_failed)}/{len(adv)} held")
    print(f"  guardrails     {dict(Counter(g for r in results for g in r.guardrails))}")
    desks = Counter(r.actual_desk for r in results if r.actual_desk)
    print(f"  desks          {dict(desks)}")
    asserted = [r for r in results if r.expected_desk]
    if asserted:
        held = sum(1 for r in asserted if r.routing_ok)
        print(f"  routing        {held}/{len(asserted)} asserted desks held"
              f"   {GREY}(* above){RESET}")

    ok = True
    if rate < min_pass:
        print(f"\n{RED}{BOLD}GATE FAILED{RESET}: {rate:.0%} < {min_pass:.0%}")
        ok = False
    # All four outcomes must be reachable. A suite that never produces
    # SIU_REFERRAL is not testing fraud routing, however green it looks.
    if missing_outcomes:
        print(f"\n{RED}{BOLD}GATE FAILED{RESET}: outcome(s) never produced: "
              f"{missing_outcomes}")
        ok = False
    # Zero tolerance on the golden gate. An adversarial failure is a guardrail
    # regression, and a guardrail regression is not something a good average
    # should be allowed to hide.
    if suite == "golden" and adv_failed:
        print(f"\n{RED}{BOLD}GATE FAILED{RESET}: adversarial case(s) regressed: "
              f"{[r.adversarial for r in adv_failed]}")
        ok = False

    if ok:
        print(f"\n{GREEN}{BOLD}GATE PASSED{RESET}")
    return 0 if ok else 1
