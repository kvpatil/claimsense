"""The two backends must agree.

The fixture and the live API are generated from one pass of generate.py, and
the whole $0-gate argument rests on the mock path being a genuine rehearsal
rather than a stub. If they can diverge, the gate measures something the
client never runs.

They DID diverge once, which is why this file exists. `keywords` — the
claimant-vocabulary field BM25 indexes — was added to corpus.json and the
fixture but never to schema.sql or the /clauses endpoint. The offline path
retrieved the wear-and-tear exclusion first and the live path did not retrieve
it at all, so claim 4407 came back DENY offline and MORE_INFO live. Every test
passed; only a live run caught it.

Skipped when the stack is not up, so `make verify` stays a $0 gate.
"""
from __future__ import annotations

import os

import pytest

from claimsense_agent.pipeline import run_pipeline
from claimsense_agent.systems import ClaimsData, SystemError_
from claimsense_agent.trace import Tracer

PLANTED = list(range(4401, 4421))


def _live_or_skip() -> ClaimsData:
    try:
        data = ClaimsData(mock=False)
        data.get_claim(4401)          # prove it actually answers
        return data
    except Exception as exc:          # noqa: BLE001 - any failure means "not up"
        pytest.skip(f"live stack unavailable ({type(exc).__name__}); "
                    "run `make up && make web` to exercise this")


@pytest.fixture(scope="module")
def mock_data():
    return ClaimsData(mock=True)


@pytest.fixture(scope="module")
def live_data():
    return _live_or_skip()


def _run(data, claim_id):
    return run_pipeline(data, claim_id, tracer=Tracer(quiet=True), brain="mock")


@pytest.mark.parametrize("claim_id", PLANTED)
def test_outcome_matches_across_backends(mock_data, live_data, claim_id):
    a, b = _run(mock_data, claim_id), _run(live_data, claim_id)
    assert a.verdict.outcome == b.verdict.outcome, (
        f"claim {claim_id}: fixture says {a.verdict.outcome}, live says "
        f"{b.verdict.outcome} — the two backends have drifted")


@pytest.mark.parametrize("claim_id", PLANTED)
def test_citations_match_across_backends(mock_data, live_data, claim_id):
    a, b = _run(mock_data, claim_id), _run(live_data, claim_id)
    assert a.verdict.cited_clause_ids == b.verdict.cited_clause_ids


@pytest.mark.parametrize("claim_id", PLANTED)
def test_verdict_source_matches_across_backends(mock_data, live_data, claim_id):
    a, b = _run(mock_data, claim_id), _run(live_data, claim_id)
    assert a.verdict.source == b.verdict.source


def test_clause_corpus_is_identical(mock_data, live_data):
    """Field-for-field, not just count.

    A count check would have passed while keywords was missing — which is
    exactly the failure this file exists to catch.
    """
    m = {c["clause_id"]: c for c in mock_data.get_clauses()}
    l = {c["clause_id"]: c for c in live_data.get_clauses()}
    assert set(m) == set(l), "clause ids differ between fixture and PAS"

    for cid, mc in m.items():
        lc = l[cid]
        for field in ("product", "section", "title", "clause_type", "body",
                      "perils", "keywords"):
            assert mc.get(field, "") == lc.get(field, ""), (
                f"{cid}.{field} differs between the fixture and the live API — "
                "a retrieval field served by one and not the other silently "
                "degrades that path")
