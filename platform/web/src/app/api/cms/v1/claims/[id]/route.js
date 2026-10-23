import { ok, requireAuth } from "@/lib/api/respond";
import { guardClaimAccess } from "@/lib/api/scope";
import { logAudit } from "@/lib/api/audit";
import { queryOne } from "@/lib/db";

export async function GET(req, { params }) {
  const auth = await requireAuth(req, "cms", "get_claim");
  if (!auth.ok) return auth.response;
  const p = auth.principal;

  const guard = await guardClaimAccess(p, params.id, "get_claim");
  if (!guard.allowed) return guard.response;

  const claim = await queryOne(
    `SELECT claim_id, claim_number, policy_id, insured_id, peril,
            date_of_loss::text, reported_at, claimed_amount_cents::bigint,
            status, assigned_adjuster_id::int, loss_state
       FROM cms.claims WHERE claim_id = $1`,
    [params.id]
  );

  await logAudit({ adjusterId: p.adjusterId, system: "cms", action: "get_claim",
                   resourceType: "claim", resourceId: params.id, decision: "allow" });
  return ok({ claim });
}
