import { ok, requireAuth } from "@/lib/api/respond";
import { guardClaimAccess } from "@/lib/api/scope";
import { logAudit } from "@/lib/api/audit";
import { query } from "@/lib/db";

// Scope-checked via the parent claim: a sub-resource must never be a way
// around the guard on the thing it belongs to.
export async function GET(req, { params }) {
  const auth = await requireAuth(req, "cms", "get_notes");
  if (!auth.ok) return auth.response;
  const p = auth.principal;

  const guard = await guardClaimAccess(p, params.id, "get_notes");
  if (!guard.allowed) return guard.response;

  const rows = await query(
    `SELECT note_id, claim_id, author_id::int, body, created_at FROM cms.claim_notes WHERE claim_id = $1 ORDER BY created_at`, [params.id]);

  await logAudit({ adjusterId: p.adjusterId, system: "cms", action: "get_notes",
                   resourceType: "claim", resourceId: params.id,
                   decision: "allow", detail: { count: rows.length } });
  return ok({ claim_id: Number(params.id), notes: rows, count: rows.length });
}
