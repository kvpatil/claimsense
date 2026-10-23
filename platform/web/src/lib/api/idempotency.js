import { createHash } from "crypto";
import { query, queryOne } from "@/lib/db";
import { apiError } from "./respond";

/** Idempotency for every write.
 *
 * A duplicated claim decision is a duplicated payment, so this is correctness,
 * not convenience.
 *
 * Three outcomes, and the third is the one that matters:
 *
 *   fresh key                  -> proceed, then record
 *   same key, same body        -> return the ORIGINAL record, 200, with
 *                                 Idempotent-Replay: true
 *   same key, DIFFERENT body   -> 409
 *
 * That last case is a client bug. Returning the first response would silently
 * discard the second intent — an adjuster who confirmed APPROVE, then changed
 * to DENY and reused the key, would be told their denial succeeded while the
 * approval stood. Refusing is the only safe answer.
 */

function fingerprint(body) {
  // Keys sorted, so a re-ordered but identical body is recognised as a replay
  // rather than treated as a conflicting one. JSON key order is not
  // meaningful and clients do not control it.
  const canonical = JSON.stringify(body, Object.keys(body ?? {}).sort());
  return createHash("sha256").update(canonical).digest("hex");
}

export function requireIdempotencyKey(req) {
  const key = req.headers.get("idempotency-key")?.trim();
  if (!key) {
    return { error: apiError(400, "idempotency_key_required",
      "This write requires an Idempotency-Key header.",
      "Send a stable unique value, e.g. 'claim-4401-decision-<uuid>'. Retrying "
      + "with the same key returns the original record instead of creating a "
      + "second one.") };
  }
  return { key };
}

/** Look for a prior write under this key. */
export async function findReplay(system, adjusterId, key, body) {
  const row = await queryOne(
    `SELECT resource_type, resource_id, response_body, request_fingerprint
       FROM platform.idempotency_keys
      WHERE adjuster_id = $1 AND system = $2 AND idem_key = $3`,
    [adjusterId, system, key]
  );
  if (!row) return { fresh: true };

  if (row.request_fingerprint !== fingerprint(body)) {
    return {
      conflict: apiError(409, "idempotency_key_reused",
        "This Idempotency-Key was already used with a different request body.",
        "Use a new key for a new request. Reusing a key with changed content "
        + "would discard one of the two intents."),
    };
  }
  return { replay: row.response_body };
}

export async function recordWrite(system, adjusterId, key, body,
                                  resourceType, resourceId, responseBody) {
  await query(
    `INSERT INTO platform.idempotency_keys
       (idem_key, system, adjuster_id, request_fingerprint,
        resource_type, resource_id, response_body)
     VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb)
     ON CONFLICT (adjuster_id, system, idem_key) DO NOTHING`,
    [key, system, adjusterId, fingerprint(body), resourceType,
     String(resourceId), JSON.stringify(responseBody)]
  );
}
