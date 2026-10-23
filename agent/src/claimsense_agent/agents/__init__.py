"""The model-judgment stages.

Every module here is a stage that INTERPRETS. None of them computes a date, a
deductible or an access decision — those live in ../determinism/ and are handed
in as facts.

Each module exposes `run(...)` returning its strict typed output from
../contracts.py, and `INSTRUCTIONS` — the system prompt the real Agents SDK
agent uses. The mock reasoner in `run()` is the deterministic stand-in for that
agent, so the pipeline, the guardrails and the scorecard are identical on both
paths and only the reasoning swaps.
"""
