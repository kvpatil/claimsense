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

# Dependencies first, so a source edit does not invalidate the layer.
COPY pyproject.toml ./
# The live extras: HTTP to the three client systems, Postgres for telemetry,
# and the Agents SDK. Installed in the image so `--live` works out of the box,
# but nothing on the default path imports them.
RUN pip install --no-cache-dir --quiet \
      "requests>=2.31" "psycopg[binary]>=3.1" "pytest>=8.0"

COPY src/ ./src/
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
