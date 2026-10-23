import { z } from "zod";
import { Cents, IsoDate, IsoDateTime, Outcome, Peril, VerdictSource } from "./common.js";

/** CMS — Claims Management System. The only system ClaimSense writes to. */

export const Claim = z.object({
  claim_id: z.number().int(),
  claim_number: z.string(),
  // Cross-system references. No foreign key behind them: PAS is another
  // vendor's database, so a claim CAN carry a policy_id that does not resolve
  // and the contract must not pretend otherwise.
  policy_id: z.number().int(),
  insured_id: z.number().int(),
  peril: Peril,
  date_of_loss: IsoDate,
  reported_at: IsoDateTime,
  claimed_amount_cents: Cents,
  status: z.enum(["intake", "investigating", "decided", "closed"]),
  assigned_adjuster_id: z.number().int().nullable(),
  loss_state: z.string().length(2),
});

export const Fnol = z.object({
  fnol_id: z.number().int(),
  claim_id: z.number().int(),
  reported_by: z.enum(["insured", "agent", "third_party"]),
  channel: z.enum(["phone", "web", "agent", "app"]),
  // The claimant's own words. Attacker-influenceable: this is where ADV-05's
  // injection arrives. It cannot be sanitised server-side, because it is
  // evidence and the adjuster must read exactly what was said.
  narrative: z.string(),
  recorded_at: IsoDateTime,
});

export const FraudSignal = z.object({
  signal_id: z.number().int(),
  claim_id: z.number().int(),
  indicator_code: z.string(),
  detail: z.string(),
  // Weight ships WITH the signal so the score is reproducible by the caller.
  // The sum is deterministic arithmetic; only its meaning is judgment.
  weight: z.number().int(),
});

export const Adjuster = z.object({
  adjuster_id: z.number().int(),
  full_name: z.string(),
  email: z.string().email(),
  // Null for seats that investigate but do not adjudicate. The confirm
  // endpoint refuses a null licence, so this is a control rather than a label.
  license_number: z.string().nullable(),
  role: z.enum(["adjuster", "siu", "supervisor"]),
  scope: z.enum(["standard", "siu", "all"]),
});

export const Decision = z.object({
  decision_id: z.number().int(),
  claim_id: z.number().int(),
  outcome: Outcome,
  source: VerdictSource,
  rationale: z.string(),
  cited_clause_ids: z.array(z.string()),
  settlement_cents: Cents.nullable(),
  confidence: z.number().min(0).max(1).nullable(),
  // Null until a licensed adjuster confirms. A row with a recommendation and
  // no confirmation is precisely what "first decision" means: produced by the
  // system, not yet owned by a human.
  confirmed_by: z.number().int().nullable(),
  confirmed_at: IsoDateTime.nullable(),
  override_outcome: Outcome.nullable(),
  override_reason: z.string().nullable(),
  created_at: IsoDateTime,
});

/** WRITE 1 — record the agent's recommendation. Idempotent.
 *
 * `source` is required and has no default. A caller that cannot say whether a
 * model or a deterministic check produced the verdict has not met the
 * milestone, and defaulting it would let that caller pass silently.
 */
export const CreateDecision = z.object({
  outcome: Outcome,
  source: VerdictSource,
  rationale: z.string().min(1),
  cited_clause_ids: z.array(z.string()).default([]),
  settlement_cents: Cents.nullable().default(null),
  confidence: z.number().min(0).max(1).optional(),
  trace_id: z.string().optional(),
}).superRefine((v, ctx) => {
  // A settlement on anything but an approval is incoherent, and the API is
  // the right place to refuse it: this is the boundary in front of money, and
  // a bug upstream must not become a payment downstream.
  if (v.settlement_cents !== null && v.outcome !== "APPROVE") {
    ctx.addIssue({ code: z.ZodIssueCode.custom, path: ["settlement_cents"],
      message: `settlement_cents must be null when outcome is ${v.outcome}` });
  }
  // The citation requirement, enforced at the contract rather than only in
  // the agent. Two independent enforcement points, because the one that
  // matters is the one in front of the database.
  if ((v.outcome === "APPROVE" || v.outcome === "DENY")
      && v.cited_clause_ids.length === 0
      && v.source === "model") {
    ctx.addIssue({ code: z.ZodIssueCode.custom, path: ["cited_clause_ids"],
      message: "a model-sourced APPROVE or DENY must cite at least one policy "
             + "clause; an uncited coverage conclusion is not acceptable" });
  }
});

/** WRITE 2 — a licensed adjuster confirms or overrides. Idempotent.
 *
 * The act the whole system defers to. `override_outcome` is where the most
 * valuable data in the product comes from: every override is a future eval
 * case, which is why the reason is required rather than optional.
 */
export const ConfirmDecision = z.object({
  adjuster_id: z.number().int(),
  override_outcome: Outcome.optional(),
  override_reason: z.string().min(10).max(1000).optional(),
}).superRefine((v, ctx) => {
  if (v.override_outcome && !v.override_reason) {
    ctx.addIssue({ code: z.ZodIssueCode.custom, path: ["override_reason"],
      message: "an override must say why — the reason becomes an eval case" });
  }
});

export const ListClaimsResponse = z.object({
  claims: z.array(Claim), count: z.number().int(),
});
export const GetClaimResponse = z.object({ claim: Claim });
export const DecisionResponse = z.object({
  decision: Decision, idempotent_replay: z.boolean().optional(),
});
