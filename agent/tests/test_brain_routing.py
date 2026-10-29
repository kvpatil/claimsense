"""Which brain runs, and what the scorecard says ran.

Two separate invariants, and the second one is a bug this file exists to keep
fixed: the pipeline used to label a run with the brain it was CONFIGURED for
rather than the one that actually reasoned, so a --live run with credentials
present printed brain=llm over numbers the mock reasoners produced.
"""
from __future__ import annotations

import pytest

from claimsense_agent import brain as brain_mod
from claimsense_agent.brain import (DEFAULT_FAST, DEFAULT_SMART, STAGE_MODEL,
                                    model_fast, model_smart)
from claimsense_agent.pipeline import _brain_label


# --- the $0 gate cannot be routed through a paid model by accident ----------

def test_mock_wins_over_present_credentials(monkeypatch):
    """--mock is what CI runs. No environment variable may override it."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAFAKE")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
    assert brain_mod.detect(force_mock=True).is_mock
    assert brain_mod.detect(force_mock=True).provider == "none"


def test_no_credentials_falls_back_to_mock(monkeypatch):
    for var in ("AWS_ACCESS_KEY_ID", "AWS_PROFILE", "OPENAI_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    assert brain_mod.detect(force_mock=False).is_mock


def test_credentials_select_the_live_brain(monkeypatch):
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAFAKE")
    cfg = brain_mod.detect(force_mock=False)
    assert not cfg.is_mock and cfg.provider == "bedrock"
    assert cfg.fast and cfg.smart


# --- model routing is the cost deliverable ----------------------------------

def test_the_smart_model_touches_exactly_one_stage():
    smart = [s for s, role in STAGE_MODEL.items() if role == "smart"]
    assert smart == ["coverage"], (
        "the smart model is spent on the money step and nowhere else; "
        f"found {smart}")
    assert DEFAULT_FAST != DEFAULT_SMART


def test_the_routing_table_holds_roles_not_model_ids():
    """Roles cannot go stale. Resolved ids captured at import time could, and
    did: the table disagreed with what ran as soon as CLAIMSENSE_MODEL_* was
    set."""
    assert set(STAGE_MODEL.values()) == {"fast", "smart"}


def test_stage_routing_resolves_through_the_config():
    cfg = brain_mod.BrainConfig(mode="llm", provider="bedrock",
                                fast="F", smart="S")
    assert cfg.for_stage("coverage") == "S"
    for stage in ("triage", "evidence", "risk", "adjudicator"):
        assert cfg.for_stage(stage) == "F", stage


# --- the env override is actually wired -------------------------------------

def test_model_ids_are_read_at_call_time_not_import_time(monkeypatch):
    """The bug this guards: brain.py is imported BEFORE systems.load_env()
    runs, so module-level os.environ.get() captured the default and the
    CLAIMSENSE_MODEL_FAST line in .env.example did nothing. A documented cost
    control that is not wired is worse than no control."""
    assert model_fast() == DEFAULT_FAST
    monkeypatch.setenv("CLAIMSENSE_MODEL_FAST", "bedrock/converse/cheaper")
    monkeypatch.setenv("CLAIMSENSE_MODEL_SMART", "bedrock/converse/dearer")
    assert model_fast() == "bedrock/converse/cheaper"
    assert model_smart() == "bedrock/converse/dearer"


def test_detect_picks_up_an_override_set_after_import(monkeypatch):
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAFAKE")
    monkeypatch.setenv("CLAIMSENSE_MODEL_FAST", "bedrock/converse/cheaper")
    cfg = brain_mod.detect(force_mock=False)
    assert cfg.fast == "bedrock/converse/cheaper"
    assert cfg.for_stage("triage") == "bedrock/converse/cheaper"


# --- the scorecard label reports what REASONED, not what was configured ----

LIVE = brain_mod.BrainConfig(mode="llm", provider="bedrock", fast="f", smart="s")
ALL_THREE = ("triage", "evidence", "coverage")


def test_a_plain_string_label_passes_through():
    assert _brain_label("mock", {}) == "mock"


def test_mock_config_is_labelled_mock():
    cfg = brain_mod.BrainConfig(mode="mock", provider="none")
    assert _brain_label(cfg, dict.fromkeys(ALL_THREE, "mock")) == "mock"


def test_all_stages_on_the_model_is_labelled_llm():
    assert _brain_label(LIVE, dict.fromkeys(ALL_THREE, "model")) == "llm"


def test_a_partial_fallback_says_which_stage_fell_back():
    label = _brain_label(LIVE, {"triage": "model", "evidence": "model",
                                "coverage": "fallback"})
    assert label == "llm (partial: coverage fell back)"


def test_total_fallback_is_not_labelled_llm():
    """The bug in plain terms: if every stage fell back, no model reasoned,
    and calling the run `llm` would misreport its own provenance."""
    label = _brain_label(LIVE, dict.fromkeys(ALL_THREE, "fallback"))
    assert "llm" not in label
    assert label == "mock (every stage fell back)"


# --- the test client cannot be talked past its own --mock -------------------

def test_test_client_mock_is_a_floor_not_a_default(monkeypatch):
    """The agent test client has a 'live brain' checkbox. While the live brain
    changed nothing this was harmless; now it spends real money, so a server
    started with --mock must refuse to be pushed live from a browser."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAFAKE")

    # The expression the handler evaluates, kept honest here rather than by
    # standing up an HTTP server inside the unit suite.
    def resolve(server_force_mock: bool, body: dict) -> bool:
        return server_force_mock or not bool(body.get("live_brain"))

    assert resolve(True, {"live_brain": True}) is True    # the floor
    assert resolve(True, {}) is True
    assert resolve(False, {"live_brain": True}) is False  # explicitly allowed
    assert resolve(False, {}) is True                     # still defaults mock

    assert brain_mod.detect(force_mock=resolve(True, {"live_brain": True})).is_mock


def test_the_handler_actually_uses_that_expression():
    """Guards the test above against drifting away from the code it mirrors."""
    import inspect

    from claimsense_agent.testclient import server
    src = inspect.getsource(server)
    assert ('force_mock = self.server.force_mock or not bool(body.get("live_brain"))'
            in src), "the test client's mock floor has moved or been removed"
