import { createHash } from "crypto";
import { queryOne } from "@/lib/db";

/** Who is calling, and which system may they call?
 *
 * A key is scoped to exactly ONE of cms / pas / dms. That is the engagement's
 * three-integration-point story made real: three vendors, three contracts,
 * three credentials, and a compromise of one does not hand over the other two.
 * A CMS key presented to PAS is a 403, not a 401 — the caller authenticated
 * fine, they are simply not permitted here, and saying so plainly is what
 * lets an agent recover instead of retrying a valid key forever.
 *
 * Keys are stored as sha256 only; the plaintext exists once, in the output of
 * `make keys`, and never reaches the database.
 */

export function hashKey(key) {
  return createHash("sha256").update(key).digest("hex");
}

function extractKey(req) {
  const auth = req.headers.get("authorization");
  if (auth) {
    const m = /^Bearer\s+(.+)$/i.exec(auth.trim());
    if (m) return m[1].trim();
  }
  const x = req.headers.get("x-api-key");
  return x ? x.trim() : null;
}

/**
 * Resolve the credential to the adjuster seat it acts as.
 * Returns { principal } | { error } — never throws on a bad key.
 */
export async function authenticate(req, system) {
  const key = extractKey(req);
  if (!key) return { error: "missing" };

  const row = await queryOne(
    `SELECT k.key_id, k.system, k.adjuster_id::int AS adjuster_id, k.label,
            a.full_name, a.email, a.role, a.scope, a.license_number, a.active
       FROM platform.api_keys k
       JOIN cms.adjusters a ON a.adjuster_id = k.adjuster_id
      WHERE k.key_hash = $1 AND k.revoked = FALSE
      LIMIT 1`,
    [hashKey(key)]
  );
  if (!row) return { error: "invalid" };
  if (!row.active) return { error: "seat_inactive" };
  // The key is valid but belongs to a different system's contract.
  if (row.system !== system) return { error: "wrong_system", presented: row.system };

  return {
    principal: {
      adjusterId: row.adjuster_id,
      system: row.system,
      fullName: row.full_name,
      email: row.email,
      role: row.role,
      scope: row.scope,
      licenseNumber: row.license_number,
      label: row.label,
    },
  };
}
