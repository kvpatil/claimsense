import { query, queryOne } from "./db";

/** Reads for the CONSOLE.
 *
 * The console talks to the database directly; the agent talks to /api/*. That
 * is not a shortcut — they are different trust boundaries. The console is
 * server-rendered code inside our own process acting for a signed-in human,
 * while the API is an authenticated edge for an autonomous caller that needs
 * per-system credentials, rate limits, idempotency and an audit row per
 * request. Routing the UI through its own HTTP API would add a hop and prove
 * nothing.
 */

export async function listClaims({ limit = 200, outcome = null } = {}) {
  return query(
    `SELECT c.claim_id, c.claim_number, c.peril, c.date_of_loss::text,
            c.reported_at, c.claimed_amount_cents::bigint, c.status,
            c.loss_state, c.policy_id,
            p.product, p.status AS policy_status,
            a.full_name AS adjuster, a.role AS adjuster_role,
            d.decision_id, d.outcome, d.source, d.confirmed_at,
            d.override_outcome, d.settlement_cents::bigint,
            d.required_desk, d.routing_reason
       FROM cms.claims c
       LEFT JOIN pas.policies p ON p.policy_id = c.policy_id
       LEFT JOIN cms.adjusters a ON a.adjuster_id = c.assigned_adjuster_id
       LEFT JOIN LATERAL (
            SELECT decision_id, outcome, source, confirmed_at,
                   override_outcome, settlement_cents, required_desk,
                   routing_reason
              FROM cms.decisions WHERE claim_id = c.claim_id
             ORDER BY created_at DESC LIMIT 1
       ) d ON TRUE
      ${outcome ? "WHERE d.outcome = $2" : ""}
      ORDER BY c.claim_id
      LIMIT $1`,
    outcome ? [limit, outcome] : [limit]
  );
}

/** Everything one claim needs, from all three systems.
 *
 * The adjuster's manual work — three systems and a lot of tab-switching —
 * done once, in one place. That is the product.
 */
export async function getClaimBundle(claimId) {
  const claim = await queryOne(
    `SELECT c.*, c.date_of_loss::text AS date_of_loss,
            c.claimed_amount_cents::bigint AS claimed_amount_cents,
            a.full_name AS adjuster_name, a.license_number,
            a.role AS adjuster_role, a.authority_limit_cents::bigint
       FROM cms.claims c
       LEFT JOIN cms.adjusters a ON a.adjuster_id = c.assigned_adjuster_id
      WHERE c.claim_id = $1`,
    [claimId]
  );
  if (!claim) return null;

  // A null policy is a REAL state, not an error: the claim/policy reference
  // crosses a vendor boundary with no foreign key behind it. The workbench
  // renders it as a finding rather than falling over (claim 4412).
  const policy = await queryOne(
    `SELECT policy_id, policy_number, product, effective_date::text,
            expiration_date::text, status, lapse_date::text,
            payment_status, premium_cents::bigint
       FROM pas.policies WHERE policy_id = $1`,
    [claim.policy_id]
  );

  const [insured, coverages, fnol, notes, signals, documents, decisions] =
    await Promise.all([
      queryOne(`SELECT insured_id, full_name, email, state, tenure_years
                  FROM pas.insureds WHERE insured_id = $1`, [claim.insured_id]),
      policy ? query(`SELECT coverage_code, limit_cents::bigint,
                             deductible_cents::bigint, coinsurance_pct
                        FROM pas.coverages WHERE policy_id = $1
                       ORDER BY coverage_code`, [claim.policy_id]) : [],
      query(`SELECT fnol_id, reported_by, channel, narrative, recorded_at
               FROM cms.fnol WHERE claim_id = $1 ORDER BY recorded_at`, [claimId]),
      query(`SELECT note_id, body, created_at FROM cms.claim_notes
              WHERE claim_id = $1 ORDER BY created_at`, [claimId]),
      query(`SELECT indicator_code, detail, weight FROM cms.fraud_signals
              WHERE claim_id = $1 ORDER BY weight DESC`, [claimId]),
      query(`SELECT document_id, doc_type, filename, uploaded_at, page_count,
                    extracted_text, is_poisoned
               FROM dms.documents WHERE claim_id = $1 ORDER BY uploaded_at`, [claimId]),
      query(`SELECT decision_id, outcome, source, rationale, cited_clause_ids,
                    settlement_cents::bigint, confidence, confirmed_by::int,
                    confirmed_at, override_outcome, override_reason, created_at
               FROM cms.decisions WHERE claim_id = $1 ORDER BY created_at DESC`,
            [claimId]),
    ]);

  return { claim, policy, insured, coverages, fnol, notes, signals,
           documents, decisions };
}

/** The clauses a decision cited, so the console shows the TEXT and not just an id.
 *
 * This is what makes a citation checkable by the adjuster confirming it. A
 * list of identifiers is a claim that grounding happened; the clause text is
 * the evidence that it did.
 */
export async function getClauses(clauseIds) {
  if (!clauseIds?.length) return [];
  return query(
    `SELECT clause_id, title, section, clause_type, body
       FROM pas.policy_clauses WHERE clause_id = ANY($1)`,
    [clauseIds]
  );
}

/** The desks a claim crosses, with who sits at each.
 *
 * Shown in the Week 1 workbench so the handoff chain is visible: most of these
 * seats cannot decide a claim at all, which is the point — a single file
 * crosses several desks and only one of them adjudicates it.
 */
export async function getDesks() {
  return query(`SELECT role, count(*)::int AS seats,
                       -- adjudicating desks are the authority ladder, not
                       -- 'holds a licence' — an appraiser holds one and
                       -- decides nothing.
                       (role IN ('adjuster','senior_adjuster','supervisor'))
                         AS can_decide,
                       max(authority_limit_cents)::bigint AS authority
                  FROM cms.adjusters WHERE active AND adjuster_id <> 5
                 GROUP BY role ORDER BY
                   CASE role WHEN 'intake' THEN 1 WHEN 'adjuster' THEN 2
                             WHEN 'senior_adjuster' THEN 3 WHEN 'supervisor' THEN 4
                             WHEN 'appraiser' THEN 5 WHEN 'siu' THEN 6
                             ELSE 7 END`);
}

export async function getAdjusters() {
  /* PEOPLE only.
   *
   * Seat 5 is the ClaimSense service account — scope 'all', no licence — and
   * it is not a person. It leaked into the "deciding as" dropdown, which both
   * broke the Week 1 story (the client's portal showing a vendor's service
   * account before the vendor arrived) and invited someone to try a seat
   * that can never confirm anything.
   *
   * Filtered on license_number rather than by id: the rule is "seats that can
   * actually decide", which is a property, not a magic number. */
  return query(`SELECT adjuster_id::int, full_name, email, license_number,
                       role, scope
                  FROM cms.adjusters
                 WHERE active AND license_number IS NOT NULL
                 ORDER BY adjuster_id`);
}

export async function queueStats() {
  const rows = await query(
    `SELECT COALESCE(d.outcome, 'UNTRIAGED') AS outcome,
            count(*)::int AS n,
            count(*) FILTER (WHERE d.confirmed_at IS NOT NULL)::int AS confirmed
       FROM cms.claims c
       LEFT JOIN LATERAL (
            SELECT outcome, confirmed_at FROM cms.decisions
             WHERE claim_id = c.claim_id ORDER BY created_at DESC LIMIT 1
       ) d ON TRUE
      GROUP BY 1 ORDER BY 1`);
  const total = rows.reduce((s, r) => s + r.n, 0);
  return { rows, total };
}

export async function recentRuns(limit = 10) {
  return query(
    `SELECT run_id, trace_id, claim_id, brain, outcome, source, duration_ms,
            guardrails_fired, cited_clause_ids, created_at
       FROM platform.agent_runs ORDER BY created_at DESC LIMIT $1`, [limit]);
}
