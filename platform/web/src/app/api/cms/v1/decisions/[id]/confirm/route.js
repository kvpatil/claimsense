import { ok, apiError, requireAuth, validationError } from "@/lib/api/respond";
import { guardConfirm } from "@/lib/api/scope";
import { logAudit } from "@/lib/api/audit";
import { findReplay, recordWrite, requireIdempotencyKey } from "@/lib/api/idempotency";
import { ConfirmDecision } from "@/lib/contracts/cms";
import { query, queryOne } from "@/lib/db";

/**
 * POST — a licensed adjuster confirms or overrides a recommendation.
 *
 * The act the entire system defers to, and the only place a claim becomes
 * decided. Three things are enforced here and nowhere else matters as much:
 *
 *   1. the seat holds an adjuster LICENCE (guardConfirm)
 *   2. the write is idempotent — confirming twice must not decide twice
 *   3. an override must carry a reason, because every override is the single
 *      most valuable training signal the product generates
 */
export async function POST(req, { params }) {
  const auth = await requireAuth(req, "cms", "confirm_decision");
  if (!auth.ok) return auth.response;
  const p = auth.principal;

  const existing = await queryOne(
    `SELECT decision_id, claim_id, outcome, confirmed_at
       FROM cms.decisions WHERE decision_id = $1`, [params.id]);
  if (!existing) {
    return apiError(404, "not_found", `Decision ${params.id} not found.`);
  }

  const guard = await guardConfirm(p, existing.claim_id);
  if (!guard.allowed) return guard.response;

  const idem = requireIdempotencyKey(req);
  if (idem.error) return idem.error;

  let raw;
  try { raw = await req.json(); }
  catch { return apiError(400, "invalid_json", "Body must be valid JSON."); }

  const parsed = ConfirmDecision.safeParse(raw);
  if (!parsed.success) return validationError(parsed);
  const body = parsed.data;

  // The key is the acting seat's, so a confirmation is always attributable to
  // the person who made it — not to whoever happened to hold the credential.
  if (body.adjuster_id !== p.adjusterId) {
    return apiError(403, "identity_mismatch",
      "adjuster_id in the body does not match the seat this key acts as.",
      `This key acts as adjuster ${p.adjusterId}. A confirmation must name the `
      + `adjuster actually making it.`);
  }

  const prior = await findReplay("cms", p.adjusterId, idem.key, raw);
  if (prior.conflict) return prior.conflict;
  if (prior.replay) {
    return ok({ ...prior.replay, idempotent_replay: true },
              { status: 200, headers: { "Idempotent-Replay": "true" } });
  }

  // Already confirmed by someone, under a different key. Not an error to
  // retry into, but it must not silently overwrite another adjuster's
  // decision — that would erase who owned the outcome.
  if (existing.confirmed_at) {
    return apiError(409, "already_confirmed",
      `Decision ${params.id} was already confirmed.`,
      "Re-confirming would overwrite the adjuster who owns this outcome. "
      + "Record a new decision instead.");
  }

  const decision = await queryOne(
    `UPDATE cms.decisions
        SET confirmed_by = $2, confirmed_at = now(),
            override_outcome = $3, override_reason = $4
      WHERE decision_id = $1
      RETURNING decision_id, claim_id, outcome, source, rationale,
                cited_clause_ids, settlement_cents::bigint, confidence,
                confirmed_by::int, confirmed_at, override_outcome,
                override_reason, created_at`,
    [params.id, p.adjusterId, body.override_outcome ?? null,
     body.override_reason ?? null]
  );

  await query(`UPDATE cms.claims SET status = 'decided' WHERE claim_id = $1`,
              [decision.claim_id]);

  const payload = { decision };
  await recordWrite("cms", p.adjusterId, idem.key, raw, "decision",
                    decision.decision_id, payload);
  await logAudit({
    adjusterId: p.adjusterId, system: "cms", action: "confirm_decision",
    resourceType: "decision", resourceId: decision.decision_id,
    decision: "allow",
    detail: { licence: p.licenseNumber,
              agent_outcome: existing.outcome,
              final_outcome: body.override_outcome ?? existing.outcome,
              overridden: Boolean(body.override_outcome) },
  });

  return ok(payload);
}
