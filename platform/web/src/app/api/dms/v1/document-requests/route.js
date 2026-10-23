import { ok, apiError, requireAuth, validationError } from "@/lib/api/respond";
import { logAudit } from "@/lib/api/audit";
import { findReplay, recordWrite, requireIdempotencyKey } from "@/lib/api/idempotency";
import { CreateDocumentRequest } from "@/lib/contracts/dms";
import { queryOne } from "@/lib/db";

/**
 * POST — ask the claimant for a document that is missing.
 *
 * What a MORE_INFO outcome produces. Idempotent for a concrete reason: a
 * retried pipeline must not send the claimant two letters asking for the same
 * police report.
 */
export async function POST(req) {
  const auth = await requireAuth(req, "dms", "create_document_request");
  if (!auth.ok) return auth.response;
  const p = auth.principal;

  const idem = requireIdempotencyKey(req);
  if (idem.error) return idem.error;

  let raw;
  try { raw = await req.json(); }
  catch { return apiError(400, "invalid_json", "Body must be valid JSON."); }

  const parsed = CreateDocumentRequest.safeParse(raw);
  if (!parsed.success) return validationError(parsed);
  const body = parsed.data;

  const prior = await findReplay("dms", p.adjusterId, idem.key, raw);
  if (prior.conflict) return prior.conflict;
  if (prior.replay) {
    return ok({ ...prior.replay, idempotent_replay: true },
              { status: 200, headers: { "Idempotent-Replay": "true" } });
  }

  const request = await queryOne(
    `INSERT INTO dms.document_requests
       (request_id, claim_id, doc_type, reason, requested_by)
     VALUES ((SELECT COALESCE(MAX(request_id),0)+1 FROM dms.document_requests),
             $1,$2,$3,$4)
     RETURNING request_id, claim_id, doc_type, reason, requested_by::int,
               requested_at, fulfilled_at`,
    [body.claim_id, body.doc_type, body.reason, p.adjusterId]
  );

  const payload = { request };
  await recordWrite("dms", p.adjusterId, idem.key, raw, "document_request",
                    request.request_id, payload);
  await logAudit({ adjusterId: p.adjusterId, system: "dms",
                   action: "create_document_request",
                   resourceType: "document_request",
                   resourceId: request.request_id, decision: "allow",
                   detail: { claim_id: body.claim_id, doc_type: body.doc_type } });
  return ok(payload, { status: 201 });
}
