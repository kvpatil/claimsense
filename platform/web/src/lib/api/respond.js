import { NextResponse } from "next/server";
import { authenticate } from "./auth";
import { logAudit } from "./audit";

/** Response envelopes and the shared guard every handler opens with. */

export function ok(data, init) {
  return NextResponse.json(data, init);
}

/**
 * The agent-readable error envelope.
 *
 * `hint` tells the caller how to RECOVER. The primary consumer is an agent,
 * and "invalid request" sends it into a retry loop while "send { outcome,
 * source, rationale }" does not.
 */
export function apiError(status, code, message, hint, init) {
  const error = { code, message };
  if (hint) error.hint = hint;
  return NextResponse.json({ error }, { ...init, status });
}

/** Zod failures, rendered so a caller can fix them without reading our source. */
export function validationError(parsed) {
  const issues = parsed.error.issues.map(
    (i) => `${i.path.join(".") || "<body>"}: ${i.message}`
  );
  return apiError(422, "invalid_body", "Request body failed contract validation.",
                  issues.join(" | "));
}

export async function requireAuth(req, system, action) {
  const result = await authenticate(req, system);

  if (result.error === "missing") {
    return { ok: false, response: apiError(401, "unauthorized",
      "No API key presented.",
      "Send 'Authorization: Bearer csk_…' or 'X-API-Key: csk_…'. Mint keys with `make keys`.") };
  }
  if (result.error === "invalid") {
    return { ok: false, response: apiError(401, "unauthorized",
      "API key not recognised or revoked.",
      "Keys are per-system. Re-mint with `make keys` and copy all three into .env.") };
  }
  if (result.error === "seat_inactive") {
    return { ok: false, response: apiError(403, "seat_inactive",
      "The adjuster seat behind this key is deactivated.") };
  }
  if (result.error === "wrong_system") {
    // 403, not 401: the credential is genuine, it is simply the wrong door.
    await logAudit({ system, action, decision: "deny",
                     reason: `key scoped to ${result.presented}` });
    return { ok: false, response: apiError(403, "wrong_system",
      `This key is scoped to the ${result.presented.toUpperCase()} contract and `
      + `cannot be used against ${system.toUpperCase()}.`,
      `Use ${system.toUpperCase()}_API_KEY for this endpoint. The three client `
      + `systems have three separate contracts and three separate credentials.`) };
  }

  return { ok: true, principal: result.principal };
}
