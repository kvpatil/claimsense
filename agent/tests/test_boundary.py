"""The deterministic/model boundary, enforced mechanically.

The architecture figure draws a line between code and model judgment. A line
that only exists in a diagram is a line that erodes: someone reaches for a
model to settle an awkward date, the diagram still shows the box, and the
client's CISO was sold a control that is no longer there.

These tests are what make the line real.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

DETERMINISM = pathlib.Path(__file__).parent.parent / "src" / "claimsense_agent" / "determinism"

# Anything that could put a model in the path of a deterministic answer.
FORBIDDEN = {"agents", "litellm", "openai", "boto3", "anthropic",
             "claimsense_agent.agents"}


def _imports(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text())
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module.split(".")[0])
            # A relative `from ..agents import x` has module="agents" only when
            # level==0; relative imports carry the package in `level`, so check
            # the raw module text too.
            if node.level and node.module.startswith("agents"):
                found.add("agents")
    return found


@pytest.mark.parametrize("path", sorted(DETERMINISM.glob("*.py")),
                         ids=lambda p: p.name)
def test_determinism_never_imports_a_model(path):
    """No module under determinism/ may reach a model, directly or indirectly."""
    offending = _imports(path) & FORBIDDEN
    assert not offending, (
        f"{path.name} imports {offending}. Identity, dates, money and access "
        "control are deterministic by contract — a model must never be in "
        "their path.")


def test_determinism_package_has_no_agent_dependency():
    """The package __init__ must not pull the agents package in either."""
    assert not _imports(DETERMINISM / "__init__.py") & FORBIDDEN


def test_money_is_integer_cents_everywhere():
    """No float arithmetic in the money module.

    A float is how a settlement ends up one cent off, and one cent off on a
    book of claims is a reconciliation nobody can close. The only decimal
    permitted is in usd(), which formats for display and computes nothing.
    """
    src = (DETERMINISM / "money.py").read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, float):
            pytest.fail(f"float literal {node.value} in money.py line {node.lineno}")
        # True division produces a float. Settlement arithmetic must floor.
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            fn = _enclosing_function(tree, node)
            assert fn == "usd" or "explain" in str(fn), (
                f"true division at money.py line {node.lineno} outside usd()/"
                "explain() — settlement arithmetic must use // on cents")


def _enclosing_function(tree, target):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for child in ast.walk(node):
                if child is target:
                    return node.name
    return None
