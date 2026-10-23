#!/usr/bin/env bash
#
# WEEK 3 — the same workflow, automated.
#
# Everything week1_demo.sh showed an adjuster doing by hand, ClaimSense now
# does: reads all three systems, establishes cover, finds the governing clause,
# weighs the fraud indicators, computes what is payable, and produces the
# decision. The adjuster confirms it.
#
# This demo runs entirely on the mock brain — no AWS account, no API key, no
# network, $0. That is the same path CI measures.
#
#   ./week3_demo.sh
#
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

BOLD=$'\033[1m'; DIM=$'\033[2m'; RESET=$'\033[0m'
CYAN=$'\033[96m'; GREEN=$'\033[92m'; RED=$'\033[91m'; YELLOW=$'\033[93m'

step() { printf "\n${BOLD}${CYAN}%s${RESET}\n" "$*"; }
note() { printf "${DIM}  %s${RESET}\n" "$*"; }
ok()   { printf "${GREEN}  ✓ %s${RESET}\n" "$*"; }
pause(){ [ "${NOPAUSE:-0}" = "1" ] || { printf "\n${DIM}  [enter]${RESET}"; read -r _; }; }

PY=$([ -x agent/.venv/bin/python ] && echo ../agent/.venv/bin/python || echo python3)

preflight() {
  local missing=0
  command -v docker >/dev/null || { printf "  ✗ docker not found\n"; missing=1; }
  docker info >/dev/null 2>&1 || { printf "  ✗ the docker daemon is not running\n"; missing=1; }
  command -v python3 >/dev/null || { printf "  ✗ python3 not found\n"; missing=1; }
  if [ "$missing" = "1" ]; then
    printf "\n  Install what is missing, then run this again.\n\n"
    exit 1
  fi
}

# Step 3 runs the boundary tests, which need pytest. Checking up front beats a
# traceback nine screens into a walkthrough.
require_pytest() {
  if ! (cd agent && PYTHONPATH=src "$PY" -c "import pytest" >/dev/null 2>&1); then
    printf "\n${YELLOW}  pytest is not available to the agent.${RESET}\n"
    printf "  Create the virtualenv first:   ${BOLD}make venv${RESET}\n\n"
    exit 1
  fi
}
agent() { (cd agent && PYTHONPATH=src "$PY" -m claimsense_agent "$@"); }

preflight
require_pytest

printf "${BOLD}Week 3 — ClaimSense: the workflow, automated${RESET}\n"
printf "${DIM}Mock brain. No key, no network, \$0 — the same path CI measures.${RESET}\n"

step "1. One claim, end to end"
note "Claim 4414 — the water loss an adjuster worked by hand in Week 1."
note "Three systems read, cover established, clause found, money computed."
pause
agent run --claim 4414 --mock
pause

step "2. search_policy_clauses — the tool that replaces the manual search"
note "In Week 1 the adjuster typed words into a search box over the form."
note "The agent gets a tool instead. Same corpus, three differences:"
echo
printf "    • pre-filtered by product and peril, so an AUTO racing\n"
printf "      exclusion can never surface on a homeowners water claim\n"
printf "    • ranked by BM25 against the claimant's own narrative\n"
printf "    • the ids it returns are RECORDED, so a citation can be\n"
printf "      checked against what was actually retrieved\n"
echo
note "That last one is what the citation guardrail enforces in step 3."
echo
printf "  ${DIM}the claim that defeated the manual search — \"the roof has been\n"
printf "  leaking\", where the form says \"deterioration\":${RESET}\n"
agent run --claim 4407 --mock 2>&1 \
  | grep -E "HO3-I-EXCL-6|finding |OUTCOME |citations " | head -5 | sed 's/^/    /'
note "Found, because clauses carry the vocabulary claimants use as well"
note "as the vocabulary the form uses."
pause

step "3. What is arithmetic and what is judgment"
note "The boundary is enforced, not described. Nothing under determinism/"
note "may import a model SDK, and the test walks the AST to prove it."
echo
(cd agent && PYTHONPATH=src "$PY" -m pytest tests/test_boundary.py -q 2>&1 | tail -3) | sed 's/^/  /'
note "Dates, deductibles, limits and access control are code. Reading the"
note "file and choosing the clause are judgment — and every judgment cites"
note "the evidence it relied on."
pause

step "4. The control that stands in front of the money"
note "--tripwire forces the Coverage stage to state a money-moving"
note "conclusion with NO citation. Same claim, same data, one flag."
echo
printf "  ${DIM}without the flag:${RESET}\n"
agent run --claim 4401 --mock 2>&1 | grep -E "OUTCOME|settlement|citations" | sed 's/^/    /'
echo
printf "  ${DIM}with it:${RESET}\n"
agent run --claim 4401 --mock --tripwire 2>&1 \
  | grep -E "⛔|OUTCOME|settlement|citations|guardrails fired" | sed 's/^/    /'
echo
note "A claim that would have settled for \$17,500 pays nothing and goes"
note "to a human. Confidently wrong became safely escalated."
pause

step "5. Prompt injection, in a document and in the claimant's own words"
printf "  ${DIM}claim 4409 — injection inside an estimate PDF:${RESET}\n"
agent run --claim 4409 --mock 2>&1 | grep -E "QUARANTINED|OUTCOME " | sed 's/^/    /'
note "Dropped before model context. It was the only estimate on file, so"
note "the claim is now incomplete — quarantine has a cost and the system"
note "pays it rather than approving on a thin file."
echo
printf "  ${DIM}claim 4420 — injection in the first notice of loss:${RESET}\n"
note "This one CANNOT be dropped: the FNOL is the claimant's evidence."
agent run --claim 4420 --mock 2>&1 \
  | grep -E "automated reader|OUTCOME |citations " | sed 's/^/    /'
note "Fenced as untrusted, read, and reported. The injection asked for"
note "APPROVE with no citation; it got a cited DENY."
pause

step "6. Arithmetic beats eloquence"
note "Claim 4410 reads as an ordinary approvable kitchen fire. The loss"
note "is one day before the policy incepted."
agent run --claim 4410 --mock 2>&1 \
  | grep -E "in force at loss|OUTCOME |source |citations " | sed 's/^/    /'
note "Stamped deterministic_fallback, not model. A verdict a date"
note "comparison produced is a different kind of output, and the schema,"
note "the type and the console all keep them apart."
pause

step "7. Which desk handles it — decided by numbers"
note "Week 1 showed seven desks and nothing working out which one a"
note "claim needs. Three comparisons settle it, and none is a reading"
note "of the file:"
echo
printf "  ${DIM}4421 — damage is 85%% of the vehicle's value:${RESET}\n"
agent run --claim 4421 --mock 2>&1 | grep -E "total loss|desk |path |OUTCOME |settlement " | sed 's/^/    /'
echo
printf "  ${DIM}4422 — \$61,000, over an adjuster's \$25k authority:${RESET}\n"
agent run --claim 4422 --mock 2>&1 | grep -E "desk |path |OUTCOME |settlement " | sed 's/^/    /'
echo
printf "  ${DIM}4418 — a total loss AND excluded:${RESET}\n"
agent run --claim 4418 --mock 2>&1 | grep -E "total loss|desk |OUTCOME " | sed 's/^/    /'
note "Routing and coverage are independent questions. There is nothing"
note "to appraise on a claim the policy does not respond to."
pause

step "8. The gate"
agent eval --suite smoke --min-pass 0.9 --mock 2>&1 | tail -9 | sed 's/^/  /'
echo
note "Twenty cases planted in the seed itself, so an eval case cannot"
note "drift from the data it is about. Three ways to fail: the rate, an"
note "outcome never produced, or any adversarial regression."
pause

step "9. The gate has teeth"
note "Regress three cases and check the exit code — which is the only"
note "thing CI reads."
cp agent/data/fixture.json /tmp/cs_fixture.bak
python3 - <<'PYEOF'
import json
d = json.load(open('agent/data/fixture.json'))
for c in ('4402', '4403', '4413'):
    d['claims'][c]['_expect'] = 'APPROVE'
json.dump(d, open('agent/data/fixture.json', 'w'))
PYEOF
set +e
agent eval --suite smoke --min-pass 0.9 --mock >/tmp/cs_gate.txt 2>&1
CODE=$?
set -e
cp /tmp/cs_fixture.bak agent/data/fixture.json
printf "    %s\n" "$(grep 'GATE' /tmp/cs_gate.txt)"
printf "    exit code: ${RED}%s${RESET}\n" "$CODE"
note "build-and-push declares needs: [test, eval, integration], so a red"
note "gate means the push job is never scheduled. Not a conditional — a"
note "dependency."

step "10. Driving it without the portal at all"
note "The agent serves its own test client. Separate port, separate"
note "process, no Next.js and no portal database involved — if this"
note "works with Claims Desk down, the pipeline is independent of it."
echo
printf "    ${BOLD}make serve${RESET}  →  http://127.0.0.1:8080\n"
echo
note "Pick a claim, pick the seat to act as, tick 'force the tripwire',"
note "and read the whole run: the narrative, the verdict, what was"
note "retrieved versus what was cited, which steps were arithmetic and"
note "which were judgment, and the spans."
pause

step "Week 3 — what was delivered"
printf "  ${BOLD}Agents SDK pipeline${RESET}     triage ➜ evidence ➜ coverage ➜ adjudicate\n"
printf "  ${BOLD}search_policy_clauses${RESET}   the manual form search, as a tool\n"
printf "  ${BOLD}Deterministic routing${RESET}   authority · total loss · referral\n"
printf "  ${BOLD}Strict typed outputs${RESET}    one dataclass per stage\n"
printf "  ${BOLD}Four guardrails${RESET}         quarantine · citation · override · PII\n"
printf "  ${BOLD}Retrieval with citations${RESET} every clause id was actually retrieved\n"
printf "  ${BOLD}20-case gate${RESET}            100%%, all four outcomes, 5/5 adversarial\n"
printf "  ${BOLD}CI blocks the push${RESET}      proven above, by exit code\n"
printf "  ${BOLD}Agent test client${RESET}       make serve — the agent, standalone\n"
echo
note "Deliverables: docs/week3/"
note "Next (Week 4): wire this into Northwind's Claims Desk."
echo
