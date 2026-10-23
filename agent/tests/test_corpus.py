"""The corpus copy must not drift from its source.

platform/db/seed/corpus.json is the source of truth and is copied to
agent/data/policy_corpus.json so the agent container needs no platform/ on
disk. A copy nobody checks is a copy that goes stale, and a stale clause
corpus means citations that point at text the console no longer shows.
"""
from __future__ import annotations

import json
import pathlib

AGENT_COPY = pathlib.Path(__file__).parent.parent / "data" / "policy_corpus.json"
SOURCE = (pathlib.Path(__file__).parent.parent.parent
          / "platform" / "db" / "seed" / "corpus.json")


def test_agent_corpus_matches_the_source():
    assert AGENT_COPY.exists(), "run `make seed`"
    if not SOURCE.exists():          # agent container: platform/ is not shipped
        return
    assert json.loads(AGENT_COPY.read_text()) == json.loads(SOURCE.read_text()), (
        "agent/data/policy_corpus.json has drifted from platform/db/seed/"
        "corpus.json — regenerate with `make seed`")


def test_clause_ids_are_unique():
    clauses = json.loads(AGENT_COPY.read_text())["clauses"]
    ids = [c["clause_id"] for c in clauses]
    assert len(ids) == len(set(ids))


def test_every_clause_carries_claimant_keywords():
    """Without them BM25 cannot bridge legal register to how people speak."""
    clauses = json.loads(AGENT_COPY.read_text())["clauses"]
    missing = [c["clause_id"] for c in clauses if not c.get("keywords")]
    assert not missing, f"clauses with no keywords: {missing}"


def test_corpus_has_both_grants_and_exclusions():
    """A corpus of only grants cannot deny and only exclusions cannot approve."""
    clauses = json.loads(AGENT_COPY.read_text())["clauses"]
    kinds = {c["clause_type"] for c in clauses}
    assert {"grant", "exclusion", "condition"} <= kinds
