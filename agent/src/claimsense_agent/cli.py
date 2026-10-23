"""ClaimSense CLI — run a claim, run the gate, or print the SDK wiring."""
from __future__ import annotations

import argparse
import os
import sys

from . import brain as brain_mod
from .pipeline import print_scorecard, run_pipeline
from .systems import ClaimsData, SystemError_
from .trace import DIM, GREY, RESET, Tracer, banner, okline


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--mock", action="store_true",
                   help="deterministic reasoners; no key, no network, $0 "
                        "(the default when no credentials are present)")
    p.add_argument("--live", action="store_true",
                   help="read the three client systems over HTTP instead of "
                        "the bundled fixture")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="claimsense-agent",
        description="ClaimSense — the claims adjudication workflow, automated. "
                    "Produces a decision; a licensed adjuster confirms it.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="work one claim end to end")
    run.add_argument("--claim", required=True)
    run.add_argument("--write", action="store_true",
                     help="land the recommendation in the claims system "
                          "(requires --live and scoped keys)")
    run.add_argument("--tripwire", action="store_true",
                     help="force an uncited money-moving conclusion so the "
                          "output guardrail can be seen to block it")
    _add_common(run)

    ev = sub.add_parser("eval", help="run the eval gate")
    ev.add_argument("--suite", default="smoke", choices=["smoke", "golden"])
    ev.add_argument("--min-pass", type=float, default=0.9)
    ev.add_argument("--claims", default="",
                    help="restrict to a comma/range list, e.g. 4401-4410")
    _add_common(ev)

    sub.add_parser("show-sdk", help="print the real Agents SDK wiring")

    ls = sub.add_parser("claims", help="list the claim queue")
    ls.add_argument("--limit", type=int, default=25)
    _add_common(ls)

    args = ap.parse_args(argv if argv is not None else sys.argv[1:])

    if args.cmd == "show-sdk":
        from .agents.sdk_runtime import SDK_REFERENCE
        print(SDK_REFERENCE)
        return 0

    # Load .env + keys.env BEFORE detecting the brain. brain.detect() reads
    # AWS_ACCESS_KEY_ID / OPENAI_API_KEY from the environment, and it runs
    # before ClaimsData — so without this, credentials sitting in keys.env were
    # invisible and --live silently fell back to the mock brain. A silent
    # fallback is the worst kind: the run succeeds and the numbers are wrong
    # about what produced them.
    from .systems import load_env
    load_env()

    cfg = brain_mod.detect(force_mock=args.mock or not args.live)
    try:
        data = ClaimsData(mock=not args.live)
    except (SystemError_, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.cmd == "claims":
        from .determinism.money import usd
        rows = data.list_claims(args.limit)
        print(f"{'claim':<8}{'peril':<12}{'date of loss':<14}{'claimed':>14}  expect")
        for c in rows:
            print(f"{c['claim_id']:<8}{c['peril']:<12}{c['date_of_loss']:<14}"
                  f"{usd(c['claimed_amount_cents']):>14}  "
                  f"{GREY}{c.get('_expect') or ''}{RESET}")
        return 0

    if args.cmd == "run":
        banner(f"ClaimSense — claim {args.claim}",
               "triage ➜ evidence ➜ coverage(+guardrails) ➜ risk ➜ adjudicate")
        print(f"{DIM}brain: {cfg.describe()}{RESET}")
        print(f"{DIM}data : {data.backend}{RESET}\n")
        if args.tripwire:
            print(f"{DIM}--tripwire: the coverage agent will state a "
                  f"money-moving conclusion with NO citation.{RESET}")
            print(f"{DIM}            watch the output guardrail block it.{RESET}\n")
        tracer = Tracer()
        try:
            result = run_pipeline(data, args.claim, tracer=tracer, brain=cfg.mode,
                                  tripwire_demo=args.tripwire)
        except SystemError_ as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        if args.write:
            from .writeback import record_run, write_back
            write_back(data, result, tracer=tracer)
            record_run(data, result)
        print_scorecard(result, tracer)
        if args.write and not data.mock:
            console = os.environ.get("CLAIMSENSE_CONSOLE_URL",
                                     "http://localhost:3200")
            okline(f"see it in the product: {console}/claims/{result.claim_id}")
        # A blocked run is a SUCCESSFUL guardrail, not a failed run. Exit 0 —
        # failing here would make `make tripwire` look broken when it is the
        # control working exactly as designed.
        return 0

    if args.cmd == "eval":
        from .evaluate import run_suite
        return run_suite(data, suite=args.suite, min_pass=args.min_pass,
                         claims=args.claims, brain=cfg.mode)

    return 1
