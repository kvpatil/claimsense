"""The agent's test client — the harness that proves it runs without the portal."""
from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from claimsense_agent.testclient.server import Handler


@pytest.fixture(scope="module")
def base():
    # Port 0 — the OS picks a free one, so a developer with :8080 already
    # bound does not get a mysterious test failure.
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    httpd.force_mock = True
    httpd.mock_data = True
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def get(base, path):
    with urllib.request.urlopen(f"{base}{path}", timeout=10) as r:
        return r.status, r.read()


def post(base, path, body):
    req = urllib.request.Request(
        f"{base}{path}", data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_page_is_served(base):
    status, body = get(base, "/")
    assert status == 200
    assert b"ClaimSense Agent Runtime" in body


def test_ping_reports_the_brain_and_backend(base):
    status, body = get(base, "/ping")
    assert status == 200
    d = json.loads(body)
    assert d["status"] == "healthy"
    assert d["brain"] == "mock"
    assert d["data_backend"] == "fixture"


def test_examples_include_the_adversarial_cases(base):
    _, body = get(base, "/examples")
    ids = {e["claim_id"] for e in json.loads(body)["examples"]}
    # The harness is for inspecting behaviour, so the cases worth inspecting
    # have to be one click away rather than something you must know to type.
    assert {4409, 4420, 4410, 4412}.issubset(ids)


def test_invoke_returns_the_whole_run(base):
    status, d = post(base, "/invoke", {"claim_id": "4414"})
    assert status == 200 and d["ok"]
    assert d["verdict"]["outcome"] == "APPROVE"
    assert d["verdict"]["cited_clause_ids"] == ["HO3-I-EXCL-3b"]
    # Everything the CLI shows, because this surface exists to inspect the
    # agent rather than to use it.
    for key in ("narrative", "triage", "evidence", "coverage", "risk",
                "checks", "spans", "decision_basis", "guardrails_fired"):
        assert key in d, f"missing {key}"
    assert d["spans"], "spans must come through for the trace view"


def test_tripwire_can_be_forced_from_the_client(base):
    """The blocked case has to be reachable from the UI, not only the CLI."""
    _, normal = post(base, "/invoke", {"claim_id": "4401"})
    assert normal["verdict"]["outcome"] == "APPROVE"
    assert normal["verdict"]["settlement_cents"] == 1_750_000

    _, blocked = post(base, "/invoke", {"claim_id": "4401", "tripwire": True})
    assert blocked["coverage"]["blocked"] is True
    assert "citation_tripwire" in blocked["guardrails_fired"]
    assert blocked["verdict"]["settlement_cents"] is None


def test_access_report_distinguishes_view_from_confirm(base):
    """Claim 4405 refers to SIU, so the SIU seat can read it and not decide it."""
    _, d = post(base, "/invoke", {"claim_id": "4405", "seat": "4"})
    a = d["access"]
    assert a["resolved"] and a["licensed"] is False
    assert a["can_view"]["allowed"] is True
    assert a["can_confirm"]["allowed"] is False
    assert "licence" in a["can_confirm"]["reason"]


def test_service_seat_reads_everything_and_confirms_nothing(base):
    _, d = post(base, "/invoke", {"claim_id": "4405", "seat": "5"})
    a = d["access"]
    assert a["can_view"]["allowed"] is True
    assert a["can_confirm"]["allowed"] is False


def test_unknown_claim_is_404_not_500(base):
    status, d = post(base, "/invoke", {"claim_id": "99999"})
    assert status == 404 and d["ok"] is False


def test_missing_claim_id_is_rejected(base):
    status, d = post(base, "/invoke", {})
    assert status == 400 and "claim_id" in d["error"]
