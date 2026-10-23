import { ok, apiError, requireAuth } from "@/lib/api/respond";
import { logAudit } from "@/lib/api/audit";
import { query } from "@/lib/db";

// GET /api/dms/v1/documents?claim_id=…
//
// Returns poisoned documents WITH the is_poisoned flag set rather than
// filtering them out. If this endpoint quietly dropped them the agent could
// never record that it refused one, and a quarantine nobody can see is a
// quarantine nobody can audit. Dropping is the guardrail's job, at the point
// where it can be logged.
export async function GET(req) {
  const auth = await requireAuth(req, "dms", "list_documents");
  if (!auth.ok) return auth.response;
  const p = auth.principal;

  const url = new URL(req.url);
  const claimId = url.searchParams.get("claim_id");
  if (!claimId) {
    return apiError(400, "missing_param", "claim_id is required.",
                    "GET /api/dms/v1/documents?claim_id=4401");
  }

  const documents = await query(
    `SELECT document_id, claim_id, doc_type, filename, uploaded_at,
            page_count, extracted_text, is_poisoned
       FROM dms.documents WHERE claim_id = $1 ORDER BY uploaded_at`,
    [claimId]
  );
  await logAudit({ adjusterId: p.adjusterId, system: "dms",
                   action: "list_documents", resourceType: "claim",
                   resourceId: claimId, decision: "allow",
                   detail: { count: documents.length,
                             poisoned: documents.filter((d) => d.is_poisoned).length } });
  return ok({ claim_id: Number(claimId), documents, count: documents.length });
}
