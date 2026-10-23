"""A standalone test client for the agent.

Served BY THE AGENT, not by the portal, and that is the point: it proves the
pipeline runs with no console, no Next.js and no portal database in the
picture. If this works and the portal is down, the agent is genuinely
independent of it.

stdlib only — http.server and json. Adding Flask here would put a dependency
in front of the one thing that is supposed to run on nothing.

    claimsense-agent serve            # http://127.0.0.1:8080
"""

from .server import serve  # noqa: F401

__all__ = ["serve"]
