"""Deterministic operations. NO MODEL EVER RUNS IN THIS PACKAGE.

Identity, access control, policy dates and money live here because they have
exactly one correct answer and that answer must not depend on sampling. The
architecture figure draws this as a separate box from model judgment; this
package is that box.

tests/test_boundary.py asserts the rule mechanically: nothing under this
package may import the agents package, litellm, or the Agents SDK. If someone
later reaches for a model to settle a date or a deductible, the build fails.
"""

from . import clock, eligibility, identity, money, risk  # noqa: F401

__all__ = ["clock", "eligibility", "identity", "money", "risk"]
