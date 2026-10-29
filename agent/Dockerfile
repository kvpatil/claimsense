# ClaimSense agent.
#
# The mock path runs on the stdlib alone, so the base image needs nothing but
# Python — and that is the point rather than an accident. `make verify` is the
# $0 gate, and a gate that cannot fail because a wheel would not build is a
# gate you can actually trust.
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src

WORKDIR /app

# The extras are named here; the PACKAGES are named only in pyproject.toml.
# Repeating the list in this file is how psycopg came to be installed in three
# places and declared in none.
#
# An editable install needs src/ present, so it lands after the copy rather
# than before it — a source edit now re-runs pip. That costs rebuild time and
# buys a single source of truth, which is the better trade for an image that
# is built in CI rather than in the inner loop (`make verify` runs against
# agent/.venv and never touches Docker).
COPY pyproject.toml ./
COPY src/ ./src/
# live = requests + psycopg (the three client systems, and the write-back).
# llm  = the Agents SDK over LiteLLM. In the image so `--live` works out of
#        the box, but nothing on the default path imports it.
# dev  = pytest, so the suite can run inside the container.
RUN pip install --no-cache-dir --quiet -e '.[live,llm,dev]'
COPY data/ ./data/
COPY tests/ ./tests/

# Non-root. The agent reads client data; there is no reason for it to be able
# to write to its own image.
RUN useradd --create-home --uid 10001 claimsense && chown -R claimsense /app
USER claimsense

# The test client, when run with `serve`.
EXPOSE 8080

# Mock brain by default: the container must be runnable with no AWS account,
# no key and no network.
ENTRYPOINT ["python3", "-m", "claimsense_agent"]
CMD ["run", "--claim", "4401", "--mock"]
