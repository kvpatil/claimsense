"""The fair-claims clock.

State unfair-claims-practices acts put an insurer on two deadlines once a claim
is reported: acknowledge it, then accept or deny it. Those deadlines are date
arithmetic on the reported-at timestamp, so they are computed here and the model
is only ever TOLD what the clock says.

This is ClaimSense's analogue of the Reg E 10-business-day clock in the class
build. The durations below are the common statutory shape (15 days to
acknowledge, 40 to decide); a real engagement would vary them per state, which
is why they are named constants and the state is carried on the claim.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

ACK_DAYS = 15
DECISION_DAYS = 40

# Per-state overrides. Empty by design: the shape is here and the data is not,
# because inventing statutory deadlines for fifty states would be fabrication
# dressed as thoroughness. A real engagement fills this from counsel.
STATE_OVERRIDES: dict[str, tuple[int, int]] = {}


@dataclass
class ClaimClock:
    reported_at: datetime
    ack_due_at: datetime
    decision_due_at: datetime
    hours_to_decision: float
    status: str          # BREACHED | RED | AMBER | GREEN
    ack_breached: bool


def _parse(ts: str | datetime) -> datetime:
    if isinstance(ts, datetime):
        dt = ts
    else:
        dt = datetime.fromisoformat(ts)
    # Naive timestamps are treated as UTC rather than rejected: the fixture and
    # Postgres agree on UTC, and a tzinfo-less value here means a serialisation
    # round trip dropped it, not that someone meant local time.
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def compute(reported_at: str | datetime, state: str = "",
            now: datetime | None = None) -> ClaimClock:
    now = now or datetime.now(timezone.utc)
    reported = _parse(reported_at)
    ack_days, decision_days = STATE_OVERRIDES.get(state, (ACK_DAYS, DECISION_DAYS))

    ack_due = reported + timedelta(days=ack_days)
    decision_due = reported + timedelta(days=decision_days)
    hours = (decision_due - now).total_seconds() / 3600.0

    if hours < 0:
        status = "BREACHED"
    elif hours <= 72:
        status = "RED"
    elif hours <= 240:
        status = "AMBER"
    else:
        status = "GREEN"

    return ClaimClock(reported_at=reported, ack_due_at=ack_due,
                      decision_due_at=decision_due, hours_to_decision=hours,
                      status=status, ack_breached=now > ack_due)
