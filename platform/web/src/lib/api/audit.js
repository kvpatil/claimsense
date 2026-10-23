import { query } from "@/lib/db";

/** Every request, allowed or denied.
 *
 * A denial is as much a record as an approval — "who tried to read what and
 * was stopped" is the question an audit actually asks, and a log that only
 * records successes cannot answer it.
 *
 * Deliberately never throws. An audit write failing must not take down the
 * request it was recording: losing one log line is bad, turning every read
 * into a 500 because the log table is full is worse. The failure goes to
 * stderr where the container's log collector will find it.
 */
export async function logAudit({
  adjusterId = null, system, action, resourceType = null, resourceId = null,
  decision = "allow", reason = null, detail = {},
}) {
  try {
    await query(
      `INSERT INTO platform.audit_log
         (adjuster_id, system, action, resource_type, resource_id,
          decision, reason, detail)
       VALUES ($1,$2,$3,$4,$5,$6,$7,$8::jsonb)`,
      [adjusterId, system, action, resourceType,
       resourceId === null ? null : String(resourceId),
       decision, reason, JSON.stringify(detail)]
    );
  } catch (err) {
    console.error("[audit] write failed:", err.message);
  }
}
