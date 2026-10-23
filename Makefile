# ClaimSense — one entry point for everything. Every target is idempotent and
# safe to re-run. `make help` lists them.
.DEFAULT_GOAL := help
SHELL := /bin/bash

PORT     ?= 3200
CLAIM    ?= 4401
DB_URL   ?= postgresql://claimsense:claimsense@localhost:5433/claimsense
CONSOLE  ?= http://localhost:$(PORT)
COMPOSE  := docker compose -f platform/db/docker-compose.yml

# Prefer the agent's venv when it exists, fall back to system python otherwise.
# The $0 gate runs on the stdlib, so a missing venv must not stop `make eval` —
# only `make test` genuinely needs pytest installed.
PY       := $(shell [ -x agent/.venv/bin/python ] && echo agent/.venv/bin/python || echo python3)

export CLAIMSENSE_DB_URL      := $(DB_URL)
export CLAIMSENSE_CONSOLE_URL := $(CONSOLE)

.PHONY: help up seed keys web web-dev agent tripwire eval golden test verify venv doctor down clean

help: ## show this list
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | \
	  awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

up: ## Postgres + the three schemas + synthetic seed + scoped keys
	$(COMPOSE) up -d
	@echo "==> waiting for Postgres…"
	@until $(COMPOSE) exec -T claimsense-db pg_isready -U claimsense >/dev/null 2>&1; do sleep 1; done
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

venv: ## create the agent venv and install dev deps (needs uv)
	cd agent && uv venv --python 3.11 .venv && \
	  uv pip install --python .venv/bin/python --quiet "pytest>=8.0"
	@echo "==> agent/.venv ready"

doctor: ## check prerequisites and report what is missing
	@echo "docker : $$(docker --version 2>/dev/null || echo MISSING)"
	@echo "agent  : $(PY)"
	@echo "node   : $$(node -v 2>/dev/null || echo MISSING)"
	@echo "python : $$(python3 -V 2>/dev/null || echo MISSING)"
	@echo "db     : $$($(COMPOSE) exec -T claimsense-db pg_isready -U claimsense 2>/dev/null || echo 'not running — make up')"

down: ## stop Postgres (data survives)
	$(COMPOSE) down

clean: ## stop Postgres AND delete the data volume
	$(COMPOSE) down -v
