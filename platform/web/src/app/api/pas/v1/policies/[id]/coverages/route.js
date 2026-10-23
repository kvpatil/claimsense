import { ok, requireAuth } from "@/lib/api/respond";
import { logAudit } from "@/lib/api/audit";
import { query } from "@/lib/db";

export async function GET(req, { params }) {
  const auth = await requireAuth(req, "pas", "get_coverages");
  if (!auth.ok) return auth.response;
  const p = auth.principal;

  const coverages = await query(
    `SELECT coverage_id, policy_id, coverage_code, limit_cents::bigint,
            deductible_cents::bigint, coinsurance_pct
       FROM pas.coverages WHERE policy_id = $1 ORDER BY coverage_code`,
    [params.id]
  );
  await logAudit({ adjusterId: p.adjusterId, system: "pas",
                   action: "get_coverages", resourceType: "policy",
                   resourceId: params.id, decision: "allow",
                   detail: { count: coverages.length } });
  return ok({ policy_id: Number(params.id), coverages });
}
