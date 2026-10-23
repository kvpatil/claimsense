"use server";

import { revalidatePath } from "next/cache";
import { query, queryOne } from "@/lib/db";
import { logAudit } from "@/lib/api/audit";

/**
 * A licensed adjuster confirms or overrides a recommendation.
 *
 * The same three rules the API enforces, because this is the same act through
 * a different door and a control that only exists on one path is not a
 * control:
 *
 *   1. the seat must hold a LICENCE
 *   2. the write is idempotent — a double-submit must not decide twice
 *   3. an override must carry a reason, because that reason is the most
 *      valuable thing this product generates: every override is an eval case
 */
export async function confirmDecision(formData) {
  const decisionId = Number(formData.get("decision_id"));
  const adjusterId = Number(formData.get("adjuster_id"));
  const override = formData.get("override_outcome") || null;
  const reason = (formData.get("override_reason") || "").trim() || null;

  const adjuster = await queryOne(
    `SELECT adjuster_id::int, full_name, role, license_number, active
       FROM cms.adjusters WHERE adjuster_id = $1`, [adjusterId]);

  if (!adjuster?.active) {
    return { error: "That adjuster seat is not active." };
  }
  if (!adjuster.license_number) {
    await logAudit({ adjusterId, system: "cms", action: "confirm_decision",
                     resourceType: "decision", resourceId: decisionId,
                     decision: "deny", reason: "no adjuster licence on this seat" });
    return { error: `${adjuster.full_name} holds no adjuster licence. Only a `
                  + `licensed adjuster may confirm a decision.` };
  }
  if (override && !reason) {
    return { error: "An override needs a reason — it becomes an evaluation case." };
  }

  const existing = await queryOne(
    `SELECT decision_id, claim_id, outcome, confirmed_at
       FROM cms.decisions WHERE decision_id = $1`, [decisionId]);
  if (!existing) return { error: "That decision no longer exists." };

  // Idempotent by state rather than by key: the console has no retry loop, but
  // a double-click is the browser's version of one, and overwriting another
  // adjuster's confirmation would erase who owned the outcome.
  if (existing.confirmed_at) {
    return { error: "This decision was already confirmed. Record a new one instead." };
  }

  await query(
    `UPDATE cms.decisions
        SET confirmed_by = $2, confirmed_at = now(),
            override_outcome = $3, override_reason = $4
      WHERE decision_id = $1 AND confirmed_at IS NULL`,
    [decisionId, adjusterId, override, reason]);

  await query(`UPDATE cms.claims SET status = 'decided' WHERE claim_id = $1`,
              [existing.claim_id]);

  await logAudit({
    adjusterId, system: "cms", action: "confirm_decision",
    resourceType: "decision", resourceId: decisionId, decision: "allow",
    detail: { licence: adjuster.license_number, agent_outcome: existing.outcome,
              final_outcome: override ?? existing.outcome,
              overridden: Boolean(override), via: "console" },
  });

  revalidatePath(`/claims/${existing.claim_id}`);
  revalidatePath("/claims");
  return { ok: true, overridden: Boolean(override) };
}
