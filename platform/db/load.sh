#!/usr/bin/env bash
# Regenerate the synthetic seed and load it, from an empty database to a working
# one. Idempotent: schema.sql drops and recreates the three schemas, so running
# this twice leaves exactly the same data rather than doubling it.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
PSQL=(docker compose -f "$REPO/docker-compose.yml" exec -T db
      psql -U claimsense -d claimsense -q -v ON_ERROR_STOP=1)

echo "==> regenerating the synthetic seed"
python3 "$HERE/seed/generate.py"

echo "==> applying schema.sql (cms · pas · dms)"
"${PSQL[@]}" < "$HERE/schema.sql"

echo "==> applying api.sql (platform)"
"${PSQL[@]}" < "$HERE/api.sql"

echo "==> loading seed.sql"
"${PSQL[@]}" < "$HERE/seed/seed.sql"

echo "==> row counts"
"${PSQL[@]}" -c "
SELECT 'pas.policies'       AS table, count(*) FROM pas.policies
UNION ALL SELECT 'pas.coverages',      count(*) FROM pas.coverages
UNION ALL SELECT 'pas.policy_clauses', count(*) FROM pas.policy_clauses
UNION ALL SELECT 'cms.claims',         count(*) FROM cms.claims
UNION ALL SELECT 'cms.fnol',           count(*) FROM cms.fnol
UNION ALL SELECT 'cms.fraud_signals',  count(*) FROM cms.fraud_signals
UNION ALL SELECT 'dms.documents',      count(*) FROM dms.documents
ORDER BY 1;"
