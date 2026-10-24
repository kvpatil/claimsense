"""Which week of the engagement this stack is running as.

Two capabilities are built and tested but belong to Week 4, not Week 3:

  * the write-back — landing a recommendation in Northwind's Claims Desk
  * the confirm/override control an adjuster uses on that recommendation

Both put ClaimSense INSIDE the value stream. Week 3's deliverable is the
capability proven standalone: the agent set on the Agents SDK, retrieval that
cites the clauses it actually retrieved, the four outcomes, containers that
start with one command, and a CI gate that blocks the image push. None of
that requires an adjuster to see anything.

So the code stays and the stage decides whether it is reachable. Building it
early is not a reason to claim it in the wrong week.

    CLAIMSENSE_STAGE=week3   (default)  the capability, standalone
    CLAIMSENSE_STAGE=week4              integrated into Claims Desk

This module is the single definition. `platform/web/src/lib/stage.js` mirrors
it for the portal, and the two are kept in step by tests rather than by
remembering.
"""
from __future__ import annotations

import os

WEEK3 = "week3"
WEEK4 = "week4"
STAGES = (WEEK3, WEEK4)

ENV_VAR = "CLAIMSENSE_STAGE"

# What becomes reachable at week4, named so the refusal message can say which
# capability the caller was reaching for rather than just "not enabled".
INTEGRATION_CAPABILITIES = (
    "write-back of recommendations into the claims management system",
    "the adjuster confirm/override control in Claims Desk",
)


class UnknownStage(ValueError):
    """The stage variable holds something that is not a stage.

    Deliberately an error rather than a fallback to week3. A typo —
    CLAIMSENSE_STAGE=wek4 — would otherwise silently disable the write-back at
    exactly the moment someone is trying to demonstrate it, and the symptom
    (a refusal naming week3) would point away from the cause.
    """


def current() -> str:
    """The stage this process is running as. Defaults to week3."""
    raw = (os.environ.get(ENV_VAR) or WEEK3).strip().lower()
    if raw not in STAGES:
        raise UnknownStage(
            f"{ENV_VAR}={raw!r} is not a stage. Expected one of "
            f"{' or '.join(STAGES)}.")
    return raw


def integration_enabled() -> bool:
    """Whether ClaimSense may reach into the client's workflow."""
    return current() == WEEK4


def refusal(capability: str) -> str:
    """Why a Week 4 capability is refused, and how to enable it.

    Names the variable and the value. A refusal that does not say how to lift
    itself sends the reader to the source to find out.
    """
    return (
        f"{capability} is Week 4 scope — it puts ClaimSense inside Northwind's "
        f"workflow, and Week 3 delivers the capability standalone.\n"
        f"This stack is running as {current()}. "
        f"Set {ENV_VAR}={WEEK4} to enable it.")
