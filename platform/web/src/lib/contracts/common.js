import { z } from "zod";

/** Shared contract vocabulary.
 *
 * These are the TYPED CONTRACTS the engagement promised. There is no
 * TypeScript in this app, so "typed" means VALIDATED AT RUNTIME: every
 * request body and every response shape passes through a schema on a real
 * request, not only at compile time.
 *
 * That is the stronger guarantee for an integration boundary. A TS interface
 * describes what a well-behaved caller sends; a Zod schema is what happens
 * when one does not. These schemas also generate the OpenAPI that
 * docs/CONTRACTS.md publishes, so the document and the enforcement are the
 * same artifact and cannot disagree.
 */

// Money ALWAYS crosses the wire as integer cents. A JSON number is a float64,
// so sending dollars invites 1234.56 arriving as 1234.5600000000001 and a
// settlement ending a cent out. int() rejects a decimal at the boundary.
export const Cents = z.number().int().describe("amount in integer cents");

export const IsoDate = z.string().regex(/^\d{4}-\d{2}-\d{2}$/)
  .describe("calendar date, YYYY-MM-DD");
export const IsoDateTime = z.string().datetime({ offset: true })
  .describe("RFC3339 timestamp with offset");

export const Peril = z.enum([
  "fire", "water", "wind", "theft", "vandalism", "earthquake",
  "collision", "liability",
]);
export const Product = z.enum(["HO3", "HO4", "AUTO"]);

export const Outcome = z.enum(["APPROVE", "DENY", "MORE_INFO", "SIU_REFERRAL"]);

// The milestone requirement, in the contract itself: a verdict the model
// produced and one a deterministic check substituted are different kinds of
// output and must never be mistaken for one another.
export const VerdictSource = z.enum(["model", "deterministic_fallback"]);

export const DocType = z.enum([
  "police_report", "photo", "estimate", "invoice", "proof_of_loss", "receipt",
]);

/** The error envelope every endpoint returns on failure.
 *
 * `hint` is not decoration. The primary caller is an agent, and an agent that
 * is told HOW to recover retries correctly instead of escalating or giving up.
 */
export const ApiError = z.object({
  error: z.object({
    code: z.string(),
    message: z.string(),
    hint: z.string().optional(),
  }),
});

/** Idempotency, stated once and referenced by every write contract. */
export const IDEMPOTENCY_RULE = `
Every write accepts an Idempotency-Key header and every write REQUIRES one.

  * Scope: the key is unique per (adjuster, system). Two seats may reuse a key
    string without colliding.
  * Replay: a repeat with the same key and the same body returns the ORIGINAL
    record, HTTP 200, with Idempotent-Replay: true. Nothing new is created.
  * Conflict: the same key with a DIFFERENT body is HTTP 409. That is a client
    bug, and returning the first response would silently discard the second
    intent.
  * Retention: keys are kept 7 days, which is longer than any retry window a
    caller should have.

This is a correctness requirement, not a nicety. A duplicated claim decision
is a duplicated payment.`.trim();
