/** Which week of the engagement this stack is running as.
 *
 * Mirrors `agent/src/claimsense_agent/stage.py` — that module carries the
 * reasoning, this one carries the same rule for the portal. Two consumers,
 * one definition, kept in step by a test rather than by remembering.
 *
 *   week3  (default)  the capability, standalone. The portal shows a
 *                     recommendation but no adjuster can act on it.
 *   week4             integrated — the confirm/override control is live.
 *
 * Server-side only. This reads process.env the same way lib/db.js does, and
 * the value must never cross to the client: a stage is a deployment fact, not
 * something a browser should be able to assert.
 */

export const WEEK3 = "week3";
export const WEEK4 = "week4";
const STAGES = [WEEK3, WEEK4];

export const STAGE_ENV_VAR = "CLAIMSENSE_STAGE";

/**
 * The stage this process is running as.
 *
 * Throws on an unrecognised value rather than falling back to week3. A typo
 * would otherwise silently hide the confirm control and the symptom — a
 * missing button — points nowhere near the cause.
 */
export function currentStage() {
  const raw = (process.env[STAGE_ENV_VAR] ?? WEEK3).trim().toLowerCase();
  if (!STAGES.includes(raw)) {
    throw new Error(
      `${STAGE_ENV_VAR}="${raw}" is not a stage. Expected ${STAGES.join(" or ")}.`
    );
  }
  return raw;
}

/** Whether ClaimSense may reach into the client's workflow. */
export function integrationEnabled() {
  return currentStage() === WEEK4;
}
