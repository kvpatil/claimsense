#!/usr/bin/env bash
#
# WEEK 1 — the client's existing system.
#
# Northwind Mutual adjudicates claims on Claims Desk. There is no automation in
# this demo and nothing is hidden to make the point: the portal simply has no
# ClaimSense in it, because in Week 1 it did not.
#
# What this shows is the problem the engagement exists to solve — three
# systems, a queue nobody has touched, and a decision that has to be assembled
# by hand every time.
#
#   ./week1_demo.sh
#
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

BOLD=$'\033[1m'; DIM=$'\033[2m'; RESET=$'\033[0m'
CYAN=$'\033[96m'; GREEN=$'\033[92m'; YELLOW=$'\033[93m'

step() { printf "\n${BOLD}${CYAN}%s${RESET}\n" "$*"; }
note() { printf "${DIM}  %s${RESET}\n" "$*"; }
ok()   { printf "${GREEN}  ✓ %s${RESET}\n" "$*"; }
pause(){ [ "${NOPAUSE:-0}" = "1" ] || { printf "\n${DIM}  [enter]${RESET}"; read -r _; }; }

psql_() { docker compose exec -T db psql -U claimsense -d claimsense -qtA "$@"; }

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

# Week 1 is the system BEFORE any automation, so the demo refuses to run
# against a database that already has recommendations in it. Showing the
# manual workflow beside twenty agent decisions would be showing nothing.
require_clean_slate() {
  local n
  n=$(psql_ -c "SELECT count(*) FROM cms.decisions;" 2>/dev/null || echo 0)
  if [ "${n:-0}" != "0" ]; then
    printf "\n${YELLOW}  This database already holds %s decision(s).${RESET}\n" "$n"
    printf "  Week 1 is the system before any automation, so it needs a clean slate.\n\n"
    printf "  Reset it with:   ${BOLD}make reset${RESET}\n\n"
    exit 1
  fi
}

printf "${BOLD}Week 1 — Northwind Mutual, Claims Desk${RESET}\n"
printf "${DIM}The existing system. Manual adjudication, no automation.${RESET}\n"
echo
printf "${DIM}  CMS   Claims Management System      the claim and its history${RESET}\n"
printf "${DIM}  PAS   Policy Administration System  what the policy covers${RESET}\n"
printf "${DIM}  DMS   Document Management System    the files on the claim${RESET}\n"
printf "${DIM}  FNOL  First Notice of Loss          the claimant's own account${RESET}\n"
printf "${DIM}  SIU   Special Investigations Unit   the fraud desk${RESET}\n"
printf "${DIM}  ACV   Actual Cash Value             what the item was worth${RESET}\n"
printf "${DIM}                                      full list: docs/GLOSSARY.md${RESET}\n"

preflight

step "1. Bring up Northwind's estate"
note "Three systems behind one portal: CMS, PAS and DMS."
docker compose up -d --wait db seed web >/dev/null 2>&1
require_clean_slate
ok "Claims Desk is up on http://localhost:3200"

step "2. The queue as an adjuster finds it"
TOTAL=$(psql_ -c "SELECT count(*) FROM cms.claims;")
WORKED=$(psql_ -c "SELECT count(*) FROM cms.decisions;")
OPEN=$(psql_ -c "SELECT to_char(sum(claimed_amount_cents)/100.0,'FM999,999,999.00') FROM cms.claims WHERE status='intake';")
printf "  %-34s %s\n" "Claims in the queue" "$TOTAL"
printf "  %-34s %s\n" "Decisions recorded" "$WORKED"
printf "  %-34s \$%s\n" "Open exposure" "$OPEN"
note "Nothing has been worked. Every one of these is a file someone"
note "has to open, read, and reason about from scratch."
pause

step "3. What working ONE claim actually involves"
note "Claim 4414 — a water loss. Watch how many systems it takes."
echo
printf "  ${YELLOW}CMS — Claims Management System${RESET}  the claim, and the first\n"
printf "       notice of loss in the claimant's own words\n"
psql_ -F' | ' -c "SELECT c.claim_number, c.peril, c.date_of_loss, to_char(c.claimed_amount_cents/100.0,'FM999,999.00')
                    FROM cms.claims c WHERE c.claim_id=4414;" | sed 's/^/    /'
psql_ -c "SELECT narrative FROM cms.fnol WHERE claim_id=4414;" | fold -s -w 72 | sed 's/^/    /'
echo
printf "  ${YELLOW}PAS — Policy Administration System${RESET}  was there cover, and how much\n"
psql_ -F' | ' -c "SELECT p.policy_number, p.product, p.status, p.effective_date, p.expiration_date
                    FROM pas.policies p JOIN cms.claims c ON c.policy_id=p.policy_id
                   WHERE c.claim_id=4414;" | sed 's/^/    /'
psql_ -F' | ' -c "
  SELECT rpad(cv.coverage_code, 6),
         rpad(CASE cv.coverage_code
                WHEN 'DWELL' THEN 'Dwelling'
                WHEN 'PP'    THEN 'Personal Property'
                WHEN 'LIAB'  THEN 'Personal Liability'
                WHEN 'ALE'   THEN 'Additional Living Expense'
                WHEN 'COLL'  THEN 'Collision'
                WHEN 'COMP'  THEN 'Comprehensive'
                ELSE cv.coverage_code END, 26),
         'limit \$' || to_char(cv.limit_cents/100.0,'FM999,999'),
         'deductible \$' || to_char(cv.deductible_cents/100.0,'FM999,999')
    FROM pas.coverages cv JOIN cms.claims c ON c.policy_id=cv.policy_id
   WHERE c.claim_id=4414 ORDER BY cv.coverage_code;" | sed 's/^/    /'
echo
printf "  ${YELLOW}DMS — Document Management System${RESET}  what has been supplied\n"
psql_ -F' | ' -c "SELECT doc_type, page_count FROM dms.documents WHERE claim_id=4414 ORDER BY doc_type;" | sed 's/^/    /'
pause

step "4. Searching the policy wording by hand"
note "The adjuster now has to answer, unaided:"
echo
printf "    • Is a burst washing-machine hose 'sudden and accidental',\n"
printf "      or is it the water damage the policy excludes?\n"
printf "    • Which clause says so? What is its number?\n"
printf "    • What is payable, net of the deductible?\n"
echo
CLAUSES=$(psql_ -c "SELECT count(*) FROM pas.policy_clauses WHERE product IN ('HO3','ALL');")
note "$CLAUSES clauses apply to this form. The portal offers a search box"
note "over the wording — http://localhost:3200/policy — and it is a plain"
note "text match. It does not know what claim you are working."
echo
WATER=$(psql_ -c "SELECT count(*) FROM pas.policy_clauses WHERE product='HO3' AND body ILIKE '%water%';")
printf "  ${YELLOW}they search \"water\"${RESET} — $WATER clauses come back, unranked:\n"
psql_ -F'  —  ' -c "SELECT clause_id, title FROM pas.policy_clauses
                     WHERE product='HO3' AND body ILIKE '%water%'
                     ORDER BY clause_id;" | sed 's/^/    /'
note "Two of those decide this claim. One excludes the loss, the next"
note "restores it, and which governs depends on reading both and"
note "noticing the second is an exception to the first. The other three"
note "are noise. Nothing in the portal says which is which."
echo
printf "  ${YELLOW}and if they search the claimant's words${RESET} — \"leaking\":\n"
HITS=$(psql_ -c "SELECT count(*) FROM pas.policy_clauses WHERE body ILIKE '%leaking%';")
printf "    %s results. The form says \"deterioration\" and \"rot\";\n" "$HITS"
printf "    the claimant said \"leaking\". The right clause is there and\n"
printf "    the search will not find it.\n"
echo
note "Nothing records which clause the decision actually rested on."
pause

step "5. A claim is not worked by one person"
note "Northwind's claims operation is seven desks, and most of them"
note "cannot decide a claim at all. SIU is the Special Investigations"
note "Unit — the fraud desk; an appraiser values a total loss:"
echo
psql_ -F' | ' -c "
  SELECT rpad(role, 16),
         count(*) || ' seat(s)',
         CASE WHEN role NOT IN ('adjuster','senior_adjuster','supervisor')
                   THEN 'does not decide claims'
              WHEN max(authority_limit_cents) IS NULL
                   THEN 'settles without limit'
              ELSE 'settles to $' || to_char(max(authority_limit_cents)/100,'FM999,999')
         END
    FROM cms.adjusters WHERE active AND adjuster_id <> 5
   GROUP BY role
   ORDER BY CASE role WHEN 'intake' THEN 1 WHEN 'adjuster' THEN 2
                      WHEN 'senior_adjuster' THEN 3 WHEN 'supervisor' THEN 4
                      WHEN 'appraiser' THEN 5 WHEN 'siu' THEN 6 ELSE 7 END;" \
  | sed 's/^/    /'
echo
note "Which desk a claim reaches is decided by NUMBERS — the amount"
note "against the adjuster's authority, the damage against the item's"
note "value, the fraud score against the referral threshold."
echo
printf "  ${YELLOW}and today nobody computes those until a human does${RESET}\n"
echo

TL=$(psql_ -c "SELECT count(*) FROM cms.claims
                WHERE acv_cents IS NOT NULL
                  AND claimed_amount_cents::numeric / acv_cents >= 0.75;")
OVER=$(psql_ -c "SELECT count(*) FROM cms.claims WHERE claimed_amount_cents > 2500000;")
printf "  %-44s %s\n" "Total losses (damage >=75%% of cash value)" "$TL"
printf "  %-44s %s\n" "Claims over an adjuster's \$25,000 authority" "$OVER"
note "Each of those is a handoff: re-read the file, re-establish the"
note "facts, wait in another queue. The adjuster who opens it first"
note "does that work before discovering they cannot finish it."
pause

step "6. Where the time goes"
note "Open the claim in the portal and work it by hand:"
echo
printf "    ${BOLD}http://localhost:3200/claims/4414${RESET}\n"
echo
note "The 'First decision' panel is an empty form. Outcome, clause"
note "identifiers typed from memory, the payable amount worked out on"
note "paper, and the letter written from scratch."
echo
AGED=$(psql_ -c "SELECT count(*) FROM cms.claims WHERE status='intake' AND reported_at < now() - interval '25 days';")
printf "  %-34s %s\n" "Claims already past 25 days" "$AGED"
note "Every one of those is accruing fair-claims exposure while it waits."

step "Week 1 — what discovery found"
printf "  ${BOLD}Three systems${RESET}  CMS, PAS, DMS — no adjuster sees a claim in one place\n"
printf "  ${BOLD}Seven desks${RESET}  and nothing works out which one a claim needs\n"
printf "  ${BOLD}No citation trail${RESET}  the clause relied on is never recorded\n"
printf "  ${BOLD}Inconsistent${RESET}  the same facts reach different adjusters differently\n"
printf "  ${BOLD}Unbounded${RESET}  the queue grows faster than it is worked\n"
echo
note "Deliverables: docs/week1/"
note "Next: week3_demo.sh — the same workflow, automated."
echo
