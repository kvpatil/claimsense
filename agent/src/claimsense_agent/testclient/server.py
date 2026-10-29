"""The test client's HTTP layer.

Four endpoints, deliberately few:

    GET  /           the single-page harness
    GET  /ping       health, so the page can show whether the runtime is up
    GET  /examples   claims worth trying, with what each one demonstrates
    POST /invoke     run the pipeline and return the full result

/invoke returns the WHOLE result — narrative, structured verdict, citations,
guardrails fired, and the spans — because the purpose of this surface is to
inspect the agent, not to use it. The portal gets a recommendation; this gets
everything that produced it.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from ..brain import detect
from ..determinism import identity
from ..pipeline import run_pipeline
from ..systems import ClaimsData, SystemError_
from ..trace import Tracer

HERE = Path(__file__).resolve().parent

# Claims worth trying, and what each one demonstrates. Ordered so the first is
# the boring one — you want to see the pipeline work before you see it refuse.
EXAMPLES = [
    (4414, "burst supply line", "the exception to the water exclusion — "
                                "same peril code as 4402, opposite outcome"),
    (4402, "surface water", "the exclusion itself"),
    (4401, "kitchen fire", "a clean approval, $17,500 payable"),
    (4409, "poisoned estimate", "ADV-01 — injection in a document, quarantined"),
    (4420, "poisoned FNOL", "ADV-05 — injection in the claimant's own words"),
    (4410, "loss before inception", "ADV-02 — arithmetic beats a plausible story"),
    (4412, "policy not in PAS", "ADV-04 — a dangling cross-system reference"),
    (4411, "claim equals the limit", "ADV-03 — the off-by-one-cent boundary"),
    (4405, "stacked fraud indicators", "referral by threshold, not by narrative"),
    (4421, "total loss", "85% of the vehicle's value — routes to an appraiser"),
    (4422, "over authority", "$61,000 exceeds an adjuster's $25k — routes up"),
]


def _access_report(data, claim_id, seat_id, refer_to_siu: bool) -> dict:
    """Whether the chosen seat could see this claim, and could decide it.

    The selector in the UI has to MEAN something or it should not be there.
    This is the RBAC surface tested in isolation: pick a seat, pick a claim,
    and see both answers — which are different questions with different
    answers. An SIU analyst can read a referred claim they could never
    adjudicate, and the ClaimSense service seat can read everything and
    adjudicate nothing.
    """
    try:
        adjuster = data.get_adjuster(seat_id)
        claim = data.get_claim(claim_id)
    except Exception:  # noqa: BLE001
        return {"seat": seat_id, "resolved": False}
    if not adjuster:
        return {"seat": seat_id, "resolved": False}

    view = identity.can_view(adjuster, claim, siu_referred=refer_to_siu)
    confirm = identity.can_confirm(adjuster, claim, siu_referred=refer_to_siu)
    return {
        "seat": int(adjuster["adjuster_id"]),
        "resolved": True,
        "name": adjuster["full_name"],
        "role": adjuster["role"],
        "scope": adjuster["scope"],
        "licensed": bool(adjuster.get("license_number")),
        "can_view": {"allowed": view.allowed, "reason": view.reason},
        "can_confirm": {"allowed": confirm.allowed, "reason": confirm.reason},
    }


def _result_payload(result, cfg, tracer) -> dict:
    """Flatten a run for inspection.

    The spans come from the TRACER, not the result: RunResult carries the
    pipeline's conclusions, and the tracer carries how it got there. They are
    deliberately separate — the portal only ever needs the former.
    """
    v, c, e, t, r = (result.verdict, result.coverage, result.evidence,
                     result.triage, result.risk)
    return {
        "ok": True,
        "claim_id": result.claim_id,
        "trace_id": result.trace_id,
        # result.brain is what REASONED; cfg.describe() is what was
        # configured. They differ when a stage fell back, and the UI needs the
        # first one to be the headline.
        "brain": result.brain,
        "stage_brains": result.stage_brains,
        "model": cfg.describe(),
        "duration_ms": round(result.duration_ms, 1),
        "narrative": v.rationale,
        "verdict": {
            "outcome": v.outcome,
            "source": v.source,
            "confidence": v.confidence,
            "settlement_cents": v.settlement_cents,
            "cited_clause_ids": v.cited_clause_ids,
            "requested_documents": v.requested_documents,
            "blocked": v.blocked,
            "blocked_reason": v.blocked_reason,
            "requires_human_confirmation": v.requires_human_confirmation,
        },
        "triage": {"peril": t.peril, "product": t.product, "severity": t.severity,
                   "clock_status": t.clock_status,
                   "days_to_decide": round(t.hours_to_decision_deadline / 24, 1)},
        "evidence": {"systems": e.source_systems, "sufficient": e.sufficient,
                     "documents_on_file": e.documents_on_file,
                     "missing_documents": e.missing_documents,
                     "quarantined": e.quarantined_document_ids,
                     "policy_resolved": e.policy_resolved},
        "coverage": {"finding": c.finding, "statement": c.statement,
                     "retrieved": c.retrieved_clause_ids,
                     "cited": c.cited_clause_ids, "blocked": c.blocked,
                     "tripwire_reason": c.tripwire_reason},
        "risk": {"score": r.score, "band": r.band, "indicators": r.indicators,
                 "interpretation": r.interpretation, "refer": r.refer_to_siu},
        "routing": None if not v.routing else {
            "desk": v.routing.desk, "reason": v.routing.reason,
            "chain": v.routing.chain, "escalated": v.routing.escalated,
            "total_loss": v.routing.total_loss,
            "damage_ratio": v.routing.damage_ratio,
        },
        "guardrails_fired": result.guardrails_fired,
        "checks": [{"name": n, "pass": ok, "note": note}
                   for n, ok, note in result.checks],
        "spans": [{"name": s["name"], "kind": s["kind"],
                   "duration_ms": s["duration_ms"], "events": s["events"][:12]}
                  for s in tracer.spans],
        "decision_basis": [{"kind": b.kind, "name": b.name, "detail": b.detail,
                            "evidence": b.evidence} for b in v.decision_basis],
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "ClaimSenseTestClient/1.0"

    # The default logger writes a line per request to stderr and drowns the
    # agent's own trace output.
    def log_message(self, fmt, *args):
        pass

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        # This harness binds loopback only (see serve()), so there is no
        # cross-origin story to get wrong.
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, payload: dict) -> None:
        self._send(code, json.dumps(payload, default=str).encode(),
                   "application/json")

    def do_GET(self):  # noqa: N802
        if self.path in ("/", "/index.html"):
            html = (HERE / "index.html").read_bytes()
            return self._send(200, html, "text/html; charset=utf-8")

        if self.path == "/ping":
            cfg = detect(force_mock=self.server.force_mock)
            backend, detail = "fixture", None
            if not self.server.mock_data:
                try:
                    ClaimsData(mock=False).get_claim(4401)
                    backend = "live"
                except Exception as exc:  # noqa: BLE001
                    backend, detail = "unavailable", str(exc)[:200]
            return self._json(200, {
                "status": "healthy", "brain": cfg.mode, "model": cfg.describe(),
                "data_backend": backend, "detail": detail,
                "now": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            })

        if self.path == "/examples":
            return self._json(200, {"examples": [
                {"claim_id": cid, "label": label, "why": why}
                for cid, label, why in EXAMPLES]})

        return self._json(404, {"ok": False, "error": "not found"})

    def do_POST(self):  # noqa: N802
        if self.path != "/invoke":
            return self._json(404, {"ok": False, "error": "not found"})

        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            return self._json(400, {"ok": False, "error": "body must be JSON"})

        claim_id = body.get("claim_id")
        if not claim_id:
            return self._json(400, {"ok": False, "error": "claim_id is required"})

        use_live_data = bool(body.get("live_data"))
        tripwire = bool(body.get("tripwire"))

        # The server's own --mock is a FLOOR, not a default the browser can
        # talk its way past. This used to be harmless because the live brain
        # changed nothing; now it spends real money, and a page left open on a
        # mock-started server must not be able to bill the client's account.
        force_mock = self.server.force_mock or not bool(body.get("live_brain"))
        cfg = detect(force_mock=force_mock)
        try:
            data = ClaimsData(mock=not use_live_data)
        except (SystemError_, FileNotFoundError) as exc:
            return self._json(503, {"ok": False, "error": str(exc),
                                    "hint": "run `make up` and `make keys`, or "
                                            "switch the data backend to the "
                                            "bundled fixture"})

        seat_id = body.get("seat")
        tracer = Tracer(quiet=True)
        try:
            result = run_pipeline(data, claim_id, tracer=tracer, brain=cfg,
                                  tripwire_demo=tripwire)
        except SystemError_ as exc:
            return self._json(404, {"ok": False, "error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            # Surfaced rather than swallowed: this is a debugging surface, and
            # a 500 with no detail is the least useful thing it could return.
            return self._json(500, {"ok": False,
                                    "error": f"{type(exc).__name__}: {exc}"})

        payload = _result_payload(result, cfg, tracer)
        if seat_id:
            payload["access"] = _access_report(
                data, claim_id, seat_id, result.risk.refer_to_siu)
        return self._json(200, payload)


def serve(port: int = 8080, *, force_mock: bool = True,
          mock_data: bool = True) -> None:
    # 127.0.0.1, never 0.0.0.0. This endpoint runs the pipeline with an
    # identity chosen in a form field and no authentication of its own — it is
    # a developer harness, and it has no business being reachable from the
    # network.
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    httpd.force_mock = force_mock
    httpd.mock_data = mock_data

    cfg = detect(force_mock=force_mock)
    print(f"\n  ClaimSense Agent Runtime — test client")
    print(f"  http://127.0.0.1:{port}")
    print(f"  brain: {cfg.describe()}")
    print(f"  data : {'bundled fixture' if mock_data else 'live client systems'}")
    print(f"\n  This is the agent serving itself. The portal is not involved.")
    print(f"  Ctrl-C to stop.\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  stopped.\n")
        httpd.shutdown()
