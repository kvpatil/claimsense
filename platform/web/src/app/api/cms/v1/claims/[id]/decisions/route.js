import { ok, apiError, requireAuth, validationError } from "@/lib/api/respond";
import { guardClaimAccess } from "@/lib/api/scope";
import { logAudit } from "@/lib/api/audit";
import { findReplay, recordWrite, requireIdempotencyKey } from "@/lib/api/idempotency";
import { CreateDecision } from "@/lib/contracts/cms";
import { query, queryOne } from "@/lib/db";

export async function GET(req, { params }) {
  const auth = await requireAuth(req, "cms", "list_decisions");
  if (!auth.ok) return auth.response;
  const guard = await guardClaimAccess(auth.principal, params.id, "list_decisions");
  if (!guard.allowed) return guard.response;

  const decisions = await query(
    `SELECT decision_id, claim_id, outcome, source, rationale, cited_clause_ids,
            settlement_cents::bigint, confidence, confirmed_by::int, confirmed_at,
            override_outcome, override_reason, created_at
       FROM cms.decisions WHERE claim_id = $1 ORDER BY created_at DESC`,
    [params.id]
  );
  return ok({ claim_id: Number(params.id), decisions, count: decisions.length });
}

/**
 * POST — record the agent's recommendation on a claim.
 *
 * This is a RECOMMENDATION, not a decision: the row lands with confirmed_by
 * NULL and stays that way until a licensed adjuster confirms it through
 * /decisions/:id/confirm. Nothing here moves money.
 */
export async function POST(req, { params }) {
  const auth = await requireAuth(req, "cms", "create_decision");
  if (!auth.ok) return auth.response;
  const p = auth.principal;

  const guard = await guardClaimAccess(p, params.id, "create_decision");
  if (!guard.allowed) return guard.response;

  const idem = requireIdempotencyKey(req);
  if (idem.error) return idem.error;

  let raw;
  try { raw = await req.json(); }
  catch { return apiError(400, "invalid_json", "Body must be valid JSON."); }

  const parsed = CreateDecision.safeParse(raw);
  if (!parsed.success) return validationError(parsed);
  const body = parsed.data;

  const prior = await findReplay("cms", p.adjusterId, idem.key, raw);
  if (prior.conflict) return prior.conflict;
  if (prior.replay) {
    await logAudit({ adjusterId: p.adjusterId, system: "cms",
                     action: "create_decision", resourceType: "claim",
                     resourceId: params.id, decision: "allow",
                     detail: { idempotent_replay: true } });
    return ok({ ...prior.replay, idempotent_replay: true },
              { status: 200, headers: { "Idempotent-Replay": "true" } });
  }

  const decision = await queryOne(
    `INSERT INTO cms.decisions
       (decision_id, claim_id, outcome, source, rationale, cited_clause_ids,
        settlement_cents, confidence)
     VALUES ((SELECT COALESCE(MAX(decision_id),0)+1 FROM cms.decisions),
             $1,$2,$3,$4,$5,$6,$7)
     RETURNING decision_id, claim_id, outcome, source, rationale,
               cited_clause_ids, settlement_cents::bigint, confidence,
               confirmed_by::int, confirmed_at, override_outcome,
               override_reason, created_at`,
    [params.id, body.outcome, body.source, body.rationale,
     body.cited_clause_ids, body.settlement_cents, body.confidence ?? null]
  );

  // The claim leaves intake the moment a recommendation exists, so the queue
  // distinguishes "nobody has looked at this" from "waiting on a human".
  await query(
    `UPDATE cms.claims SET status = 'investigating'
      WHERE claim_id = $1 AND status = 'intake'`, [params.id]);

  const payload = { decision };
  await recordWrite("cms", p.adjusterId, idem.key, raw, "decision",
                    decision.decision_id, payload);
  await logAudit({ adjusterId: p.adjusterId, system: "cms",
                   action: "create_decision", resourceType: "decision",
                   resourceId: decision.decision_id, decision: "allow",
                   detail: { outcome: body.outcome, source: body.source,
                             trace_id: body.trace_id ?? null } });

  return ok(payload, { status: 201 });
}
