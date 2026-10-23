import { ok, apiError, requireAuth } from "@/lib/api/respond";
import { logAudit } from "@/lib/api/audit";
import { queryOne } from "@/lib/db";

// GET /api/pas/v1/policies/:id
//
// 404 on a missing policy is a CONTRACTUAL outcome, not an error condition.
// The claim/policy reference crosses a vendor boundary with no foreign key
// behind it, so a dangling id is reachable in production (claim 4412 is the
// planted case). The agent treats this 404 as "policy not resolvable" and
// reports it; it must never be a 500.
export async function GET(req, { params }) {
  const auth = await requireAuth(req, "pas", "get_policy");
  if (!auth.ok) return auth.response;
  const p = auth.principal;

  const policy = await queryOne(
    `SELECT policy_id, policy_number, insured_id::int, product,
            effective_date::text, expiration_date::text, status,
            lapse_date::text, premium_cents::bigint, payment_status
       FROM pas.policies WHERE policy_id = $1`,
    [params.id]
  );

  await logAudit({ adjusterId: p.adjusterId, system: "pas", action: "get_policy",
                   resourceType: "policy", resourceId: params.id,
                   decision: "allow", detail: { found: Boolean(policy) } });

  if (!policy) {
    return apiError(404, "policy_not_found",
      `No policy ${params.id} in the policy administration system.`,
      "The claim may carry a stale or mistyped policy reference. Report this "
      + "rather than proceeding — coverage cannot be assessed without a form.");
  }
  return ok({ policy });
}
