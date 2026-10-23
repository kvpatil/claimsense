"""Console tracing — spans, by hand.

This is the hand-rolled version of what AgentCore Observability gives you
managed: every model call, tool call, handoff and guardrail is a span you can
read. It is the 3am incident evidence and the client's audit trail, and in this
build it is also how a reader sees the deterministic/judgment boundary actually
being crossed rather than being told it exists.

Colour degrades to nothing when stdout is not a TTY, so CI logs stay readable.
"""
from __future__ import annotations

import os
import sys
import time
import uuid
from contextlib import contextmanager

_TTY = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def _c(code: str) -> str:
    return code if _TTY else ""


BOLD = _c("\033[1m");  DIM = _c("\033[2m");   RESET = _c("\033[0m")
RED = _c("\033[91m");  GREEN = _c("\033[92m"); YELLOW = _c("\033[93m")
BLUE = _c("\033[94m"); MAGENTA = _c("\033[95m"); CYAN = _c("\033[96m")
GREY = _c("\033[90m")

# One glyph per span kind. `code` and `agent` are deliberately different marks:
# the whole point of the architecture is that a reader can see which steps were
# arithmetic and which were judgment, and the trace is where that shows.
_ICON = {"tool": "⛁", "agent": "◆", "code": "▣", "handoff": "➜",
         "guardrail": "🛡", "write": "✍", "retrieval": "⌕"}
_COLOR = {"tool": CYAN, "agent": BLUE, "code": MAGENTA, "handoff": YELLOW,
          "guardrail": GREEN, "write": GREEN, "retrieval": CYAN}


def banner(title: str, sub: str = "") -> None:
    w = 72
    print(f"{BOLD}{BLUE}╔{'═' * w}╗{RESET}")
    print(f"{BOLD}{BLUE}║ {title:<{w - 1}}║{RESET}")
    if sub:
        print(f"{BLUE}║ {RESET}{DIM}{sub:<{w - 1}}{RESET}{BLUE}║{RESET}")
    print(f"{BOLD}{BLUE}╚{'═' * w}╝{RESET}")


def blocked(msg: str) -> None:
    print(f"{RED}{BOLD}    ⛔ {msg}{RESET}")


def okline(msg: str) -> None:
    print(f"{GREEN}    ✓ {msg}{RESET}")


def warnline(msg: str) -> None:
    print(f"{YELLOW}    ! {msg}{RESET}")


class Tracer:
    """Collects spans for the scorecard while printing them as they happen."""

    def __init__(self, quiet: bool = False):
        self.trace_id = uuid.uuid4().hex[:12]
        self.quiet = quiet
        self.spans: list[dict] = []
        self._t0 = time.perf_counter()

    @contextmanager
    def span(self, name: str, kind: str = "agent", detail: str = ""):
        t0 = time.perf_counter()
        sid = uuid.uuid4().hex[:8]
        if not self.quiet:
            icon, color = _ICON.get(kind, "·"), _COLOR.get(kind, "")
            print(f"{color}{icon} {name}{RESET} {GREY}[{kind}] span_{sid}{RESET}")
            if detail:
                for ln in detail.splitlines():
                    print(f"    {ln}")
        rec = _Span(self, kind)
        try:
            yield rec
        finally:
            ms = (time.perf_counter() - t0) * 1000
            self.spans.append({"span_id": sid, "name": name, "kind": kind,
                               "duration_ms": round(ms, 2), "events": rec.events})

    def total_ms(self) -> float:
        return (time.perf_counter() - self._t0) * 1000


class _Span:
    def __init__(self, tracer: Tracer, kind: str):
        self._tracer = tracer
        self.kind = kind
        self.events: list[str] = []

    def event(self, msg: str, level: str = "info") -> None:
        self.events.append(msg)
        if self._tracer.quiet:
            return
        mark = {"ok": f"{GREEN}✓{RESET}", "warn": f"{YELLOW}!{RESET}",
                "block": f"{RED}⛔{RESET}", "cite": f"{CYAN}§{RESET}",
                "tool": f"{CYAN}·{RESET}", "info": f"{GREY}·{RESET}"}.get(level, " ")
        print(f"    {mark} {msg}")

    def kv(self, key: str, value) -> None:
        self.events.append(f"{key}={value}")
        if not self._tracer.quiet:
            print(f"    {GREY}{key:<22}{RESET} {value}")
