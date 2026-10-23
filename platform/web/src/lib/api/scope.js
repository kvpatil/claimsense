import { queryOne } from "@/lib/db";
import { apiError } from "./respond";
import { logAudit } from "./audit";

/** Row-level access, enforced HERE — in the integration layer, never by a model.
 *
 * This is the control the client's security review is actually buying. A model
 * asked whether a seat may see a claim will answer plausibly and occasionally
 * wrongly, and "plausibly" is not a control. The rules below are the same ones
 * the agent's determinism/identity.py applies, restated at the API boundary so
 * that bypassing the agent does not bypass the check.
 */

export async function guardClaimAccess(principal, claimId, action) {
  const claim = await queryOne(
    `SELECT c.claim_id, c.assigned_adjuster_id::int AS assigned_adjuster_id,
            EXISTS (SELECT 1 FROM cms.decisions d
                     WHERE d.claim_id = c.claim_id
                       AND d.outcome = 'SIU_REFERRAL') AS siu_referred
       FROM cms.claims c WHERE c.claim_id = $1`,
    [claimId]
  );

  if (!claim) {
    return { allowed: false, response: apiError(404, "not_found",
      `Claim ${claimId} does not exist.`) };
  }

  const deny = async (reason) => {
    await logAudit({ adjusterId: principal.adjusterId, system: principal.system,
                     action, resourceType: "claim", resourceId: claimId,
                     decision: "deny", reason });
    return { allowed: false, response: apiError(403, "forbidden",
      "This seat may not access that claim.", reason) };
  };

  if (principal.scope === "all") return { allowed: true, claim };

  if (principal.scope === "siu") {
    if (!claim.siu_referred) {
      return deny("SIU scope is limited to claims referred to the unit");
    }
    return { allowed: true, claim };
  }

  const assigned = claim.assigned_adjuster_id;
  if (assigned !== null && assigned !== principal.adjusterId) {
    return deny(`claim is assigned to adjuster ${assigned}`);
  }
  return { allowed: true, claim };
}

/**
 * May this seat CONFIRM a decision?
 *
 * A different question from "may they see it", with a different answer. The
 * licence is a property of the PERSON, not of the role: an SIU analyst can
 * read a referred claim all day and may never adjudicate one.
 */
export async function guardConfirm(principal, claimId) {
  const view = await guardClaimAccess(principal, claimId, "confirm_decision");
  if (!view.allowed) return view;

  if (!principal.licenseNumber) {
    await logAudit({ adjusterId: principal.adjusterId, system: principal.system,
                     action: "confirm_decision", resourceType: "claim",
                     resourceId: claimId, decision: "deny",
                     reason: "no adjuster licence on this seat" });
    return { allowed: false, response: apiError(403, "licence_required",
      "Only a licensed adjuster may confirm a claim decision.",
      "This seat holds no licence number. Confirmation is the act the system "
      + "defers to a human, and it requires a licensed one.") };
  }
  if (!["adjuster", "supervisor"].includes(principal.role)) {
    return { allowed: false, response: apiError(403, "role_forbidden",
      `Role '${principal.role}' may not confirm decisions.`) };
  }
  return { allowed: true, claim: view.claim };
}
