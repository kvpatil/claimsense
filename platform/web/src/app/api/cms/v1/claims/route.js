import { ok, requireAuth } from "@/lib/api/respond";
import { logAudit } from "@/lib/api/audit";
import { query } from "@/lib/db";

// GET /api/cms/v1/claims — the queue, scoped to what this seat may see.
// Scoping happens in SQL rather than by filtering after the fact: a seat must
// never receive a row it is not entitled to, not even to have it removed.
export async function GET(req) {
  const auth = await requireAuth(req, "cms", "list_claims");
  if (!auth.ok) return auth.response;
  const p = auth.principal;

  const url = new URL(req.url);
  const limit = Math.min(Number(url.searchParams.get("limit") ?? 50), 200);
  const status = url.searchParams.get("status");

  const where = [];
  const params = [];
  if (p.scope === "standard") {
    params.push(p.adjusterId);
    where.push(`(c.assigned_adjuster_id IS NULL OR c.assigned_adjuster_id = $${params.length})`);
  } else if (p.scope === "siu") {
    where.push(`EXISTS (SELECT 1 FROM cms.decisions d
                         WHERE d.claim_id = c.claim_id
                           AND d.outcome = 'SIU_REFERRAL')`);
  }
  if (status) { params.push(status); where.push(`c.status = $${params.length}`); }
  params.push(limit);

  const claims = await query(
    `SELECT c.claim_id, c.claim_number, c.policy_id, c.insured_id, c.peril,
            c.date_of_loss::text, c.reported_at, c.claimed_amount_cents::bigint,
            c.status, c.assigned_adjuster_id::int, c.loss_state,
            d.outcome AS latest_outcome, d.source AS latest_source,
            d.confirmed_at
       FROM cms.claims c
       LEFT JOIN LATERAL (
            SELECT outcome, source, confirmed_at FROM cms.decisions
             WHERE claim_id = c.claim_id ORDER BY created_at DESC LIMIT 1
       ) d ON TRUE
      ${where.length ? "WHERE " + where.join(" AND ") : ""}
      ORDER BY c.claim_id
      LIMIT $${params.length}`,
    params
  );

  await logAudit({ adjusterId: p.adjusterId, system: "cms", action: "list_claims",
                   resourceType: "claim", decision: "allow",
                   detail: { count: claims.length, scope: p.scope } });
  return ok({ claims, count: claims.length });
}
