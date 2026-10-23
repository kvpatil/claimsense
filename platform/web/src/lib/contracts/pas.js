import { z } from "zod";
import { Cents, IsoDate, Peril, Product } from "./common.js";

/** PAS — Policy Administration System. READ-ONLY to ClaimSense.
 *
 * There is no write contract in this file and that is deliberate: the agent
 * reads cover, it never alters it. A claims co-pilot that could edit a policy
 * could manufacture the coverage it then finds.
 */

export const Policy = z.object({
  policy_id: z.number().int(),
  policy_number: z.string(),
  insured_id: z.number().int(),
  product: Product,
  effective_date: IsoDate,
  expiration_date: IsoDate,
  status: z.enum(["active", "lapsed", "cancelled"]),
  // Non-null means cover ceased before the term ended. A loss on or after this
  // date has no cover even though it falls inside the policy period, which is
  // the distinction a naive term check misses.
  lapse_date: IsoDate.nullable(),
  premium_cents: Cents,
  payment_status: z.enum(["current", "late", "delinquent"]),
});

export const Coverage = z.object({
  coverage_id: z.number().int(),
  policy_id: z.number().int(),
  coverage_code: z.enum(["DWELL", "PP", "LIAB", "ALE", "COLL", "COMP"]),
  limit_cents: Cents,
  deductible_cents: Cents,
  coinsurance_pct: z.number().int().min(0).max(100),
});

export const PolicyClause = z.object({
  // A human-meaningful id, not a serial. 'HO3-I-EXCL-3b' is what a coverage
  // opinion cites and what an adjuster looks up in the paper policy; an opaque
  // integer would make a wrong citation impossible to spot by eye.
  clause_id: z.string(),
  product: z.union([Product, z.literal("ALL")]),
  section: z.string(),
  title: z.string(),
  clause_type: z.enum(["grant", "exclusion", "condition", "definition", "limit"]),
  body: z.string(),
  perils: z.array(Peril),
  keywords: z.string().optional(),
});

export const GetPolicyResponse = z.object({ policy: Policy });
export const GetCoveragesResponse = z.object({
  policy_id: z.number().int(),
  coverages: z.array(Coverage),
});
export const GetClausesResponse = z.object({
  clauses: z.array(PolicyClause),
  count: z.number().int(),
});
