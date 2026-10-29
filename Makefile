# ClaimSense — one entry point for everything. Every target is idempotent and
# safe to re-run. `make help` lists them.
.DEFAULT_GOAL := help
SHELL := /bin/bash

PORT     ?= 3200
CLAIM    ?= 4401
DB_URL   ?= postgresql://claimsense:claimsense@localhost:5433/claimsense
CONSOLE  ?= http://localhost:$(PORT)
# ONE compose file, at the root. There used to be a second under
# platform/db/ and the two drifted immediately: the root stack named the
# service `db` while the other named it `claimsense-db`, so `make keys`
# started failing against a stack that was plainly running.
COMPOSE  := docker compose

# Prefer the agent's venv when it exists, fall back to system python otherwise.
# The $0 gate runs on the stdlib, so a missing venv must not stop `make eval` —
# only `make test` genuinely needs pytest installed.
PY       := $(shell [ -x agent/.venv/bin/python ] && echo agent/.venv/bin/python || echo python3)

# week3 (default) | week4. Gates the write-back and the adjuster confirm
# control — see agent/src/claimsense_agent/stage.py.
STAGE    ?= week3

export CLAIMSENSE_DB_URL      := $(DB_URL)
export CLAIMSENSE_CONSOLE_URL := $(CONSOLE)
export CLAIMSENSE_STAGE       := $(STAGE)

.PHONY: help setup up seed keys web web-dev agent serve tripwire eval golden test verify venv show-sdk doctor reset down clean

help: ## show this list
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | \
	  awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

up: ## Postgres + the three schemas + synthetic seed + scoped keys
	$(COMPOSE) up -d --wait db
	@echo "==> waiting for Postgres…"
	@until $(COMPOSE) exec -T db pg_isready -U claimsense >/dev/null 2>&1; do sleep 1; done
	@./platform/db/load.sh
	@$(MAKE) --no-print-directory keys
	@echo ""
	@echo "==> ready. next: make agent   (or make web for the console)"

seed: ## regenerate + reload the synthetic seed
	@./platform/db/load.sh

keys: ## mint a scoped key per client system (printed once)
	@python3 platform/db/mint_keys.py

web: ## build + serve the adjuster console on :$(PORT)
	cd platform/web && npm install --silent && npm run build && PORT=$(PORT) npm run start

web-dev: ## hot-reload the console instead
	cd platform/web && npm install --silent && PORT=$(PORT) npm run dev

agent: ## work claim $(CLAIM) end to end (mock brain — no key, no network)
	cd agent && PYTHONPATH=src ../$(PY) -m claimsense_agent run --claim $(CLAIM) --mock

tripwire: ## the BLOCKED case: force an uncited money claim and watch it fail closed
	cd agent && PYTHONPATH=src ../$(PY) -m claimsense_agent run --claim $(CLAIM) --mock --tripwire

eval: ## the 20-case gate CI runs on every PR
	cd agent && PYTHONPATH=src ../$(PY) -m claimsense_agent eval --suite smoke --min-pass 0.9 --mock

serve: ## the agent test client on :8080 (no portal involved)
	cd agent && PYTHONPATH=src ../$(PY) -m claimsense_agent serve --mock

show-sdk: ## print the real OpenAI Agents SDK wiring
	@cd agent && PYTHONPATH=src ../$(PY) -m claimsense_agent show-sdk

golden: ## the full suite incl. adversarial — the release gate
	cd agent && PYTHONPATH=src ../$(PY) -m claimsense_agent eval --suite golden --min-pass 0.95 --mock

test: ## the agent's pytest suite
	cd agent && PYTHONPATH=src ../$(PY) -m pytest -q

verify: ## the $$0 gate: prerequisites + eval + unit tests. Run this first.
	@$(MAKE) --no-print-directory doctor
	@echo
	@$(MAKE) --no-print-directory eval
	@echo
	@$(MAKE) --no-print-directory test
	@echo "verify: OK"

setup: ## one-time: config files + the agent venv
	@if [ -f .env ]; then echo "    .env       exists, left alone"; \
	 else cp .env.example .env; echo "    .env       created from .env.example"; fi
	@if [ -f keys.env ]; then echo "    keys.env   exists, left alone"; \
	 else cp keys.env.example keys.env && chmod 600 keys.env; \
	   echo "    keys.env   created (mode 0600, gitignored)"; fi
	@$(MAKE) --no-print-directory venv
	@echo ""
	@echo "    Both demos run with keys.env empty. Next:"
	@echo "      docker compose up -d --wait"
	@echo "      ./week1_demo.sh"
	@echo ""

# pytest for the suite, plus the LIVE extras. The mock path needs none of them
# — that is the point of it — but a developer venv that cannot reach the live
# systems silently SKIPS the backend-parity tests, and a skipped test looks
# exactly like a passing one.
#
# Idempotent: uv venv refuses to overwrite, so create only when missing and
# always (re)install. `make setup` calls this, and people re-run setup.
# The package list lives in agent/pyproject.toml and nowhere else. It used to
# be repeated here, in agent/Dockerfile and twice in the CI workflow — four
# copies, which had already drifted: psycopg was installed by all of them and
# declared by none, so `pip install -e '.[live]'` gave you a venv where the
# write-back died on import.
venv: ## create the agent venv and install dev deps (needs uv)
	@cd agent && [ -x .venv/bin/python ] || uv venv --python 3.11 .venv
	@cd agent && uv pip install --python .venv/bin/python --quiet -e '.[live,dev]'
	@echo "==> agent/.venv ready (pytest + live extras)"

venv-llm: venv ## add the OpenAI Agents SDK, for `run --live` with a real model
	@cd agent && uv pip install --python .venv/bin/python --quiet -e '.[live,llm,dev]'
	@echo "==> agent/.venv ready (+ Agents SDK over LiteLLM)"
	@echo "    tests/test_sdk_runtime.py now runs instead of skipping."
	@echo "    'run --live' needs AWS credentials in keys.env to reach Bedrock;"
	@echo "    without them each stage falls back and says so on the scorecard."

doctor: ## check prerequisites and report what is missing
	@echo "docker : $$(docker --version 2>/dev/null || echo MISSING)"
	@echo "agent  : $(PY)"
	@echo "stage  : $(STAGE)$(if $(filter week3,$(STAGE)), (write-back and confirm control gated off),)"
	@echo "node   : $$(node -v 2>/dev/null || echo MISSING)"
	@echo "python : $$(python3 -V 2>/dev/null || echo MISSING)"
	@echo "db     : $$($(COMPOSE) exec -T db pg_isready -U claimsense 2>/dev/null || echo 'not running — make up')"

reset: ## wipe decisions and return the queue to its Week 1 state
	@$(COMPOSE) exec -T db psql -U claimsense -d claimsense -q -c \
	  "TRUNCATE cms.decisions; TRUNCATE dms.document_requests; \
	   TRUNCATE platform.agent_runs; TRUNCATE platform.idempotency_keys; \
	   UPDATE cms.claims SET status='intake';"
	@echo "==> queue reset: no decisions, every claim back to intake"

down: ## stop Postgres (data survives)
	$(COMPOSE) down

clean: ## stop Postgres AND delete the data volume
	$(COMPOSE) down -v
