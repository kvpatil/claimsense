"use client";

import { useState, useTransition } from "react";
import { confirmDecision } from "./actions";
import { OUTCOME_STYLE } from "@/lib/format";

const OUTCOMES = ["APPROVE", "DENY", "MORE_INFO", "SIU_REFERRAL"];

/**
 * The confirm / override control — the act the whole system defers to.
 *
 * Two deliberate choices in the interaction:
 *
 *   * Confirming is ONE click and overriding takes three. The draft is usually
 *     right, and making the common path cheap is how an adjuster gets through
 *     a queue. But the override must not be so cheap it happens by accident.
 *   * The reason box is required and the label says why it is being asked for.
 *     An adjuster who knows their correction trains the system writes a better
 *     reason than one who thinks they are filling in a form.
 */
export default function ConfirmPanel({ decision, adjusters }) {
  const [mode, setMode] = useState(null);      // null | "override"
  const [override, setOverride] = useState("");
  const [reason, setReason] = useState("");
  const [seat, setSeat] = useState(
    adjusters.find((a) => a.license_number)?.adjuster_id ?? adjusters[0]?.adjuster_id);
  const [error, setError] = useState(null);
  const [pending, start] = useTransition();

  const current = adjusters.find((a) => a.adjuster_id === Number(seat));
  const unlicensed = current && !current.license_number;

  function submit(withOverride) {
    setError(null);
    const fd = new FormData();
    fd.set("decision_id", decision.decision_id);
    fd.set("adjuster_id", seat);
    if (withOverride) {
      fd.set("override_outcome", override);
      fd.set("override_reason", reason);
    }
    start(async () => {
      const res = await confirmDecision(fd);
      if (res?.error) setError(res.error);
      else { setMode(null); setOverride(""); setReason(""); }
    });
  }

  if (decision.confirmed_at) {
    return (
      <div className="rounded-lg bg-note px-4 py-3 text-sm">
        <p className="text-ink">
          Confirmed {decision.override_outcome
            ? <>as <strong>{OUTCOME_STYLE[decision.override_outcome]?.label}</strong>,
                overriding the recommendation</>
            : "as recommended"}.
        </p>
        {decision.override_reason && (
          <p className="text-muted mt-1.5 italic">“{decision.override_reason}”</p>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <label htmlFor="seat" className="text-muted">Acting as</label>
        <select id="seat" value={seat} onChange={(e) => setSeat(e.target.value)}
          className="rounded-lg border border-line bg-note px-2.5 py-1.5 text-ink
                     focus:border-accent focus:outline-none">
          {adjusters.map((a) => (
            <option key={a.adjuster_id} value={a.adjuster_id}>
              {a.full_name} — {a.license_number ? a.role : `${a.role}, no licence`}
            </option>
          ))}
        </select>
      </div>

      {unlicensed && (
        <p className="text-sm text-warn">
          This seat holds no adjuster licence and cannot confirm a decision.
          Confirmation is the act the system defers to a human, and it requires
          a licensed one.
        </p>
      )}

      {mode !== "override" ? (
        <div className="flex flex-wrap gap-2">
          <button onClick={() => submit(false)} disabled={pending || unlicensed}
            className="px-4 py-2 rounded-lg bg-accent text-paper text-sm font-semibold
                       disabled:opacity-40 disabled:cursor-not-allowed hover:opacity-90">
            {pending ? "Confirming…" : "Confirm this recommendation"}
          </button>
          <button onClick={() => setMode("override")} disabled={pending || unlicensed}
            className="px-4 py-2 rounded-lg border border-line text-sm text-muted
                       hover:border-accent hover:text-accent disabled:opacity-40">
            Decide differently
          </button>
        </div>
      ) : (
        <div className="space-y-3 rounded-lg border border-line p-4 bg-note">
          <div>
            <span className="text-xs uppercase tracking-wide text-muted block mb-1.5">
              Your decision
            </span>
            <div className="flex flex-wrap gap-1.5">
              {OUTCOMES.map((o) => (
                <button key={o} onClick={() => setOverride(o)}
                  className={`px-2.5 py-1 rounded-lg border text-sm transition-colors ${
                    override === o ? "border-accent bg-accent text-paper font-semibold"
                                   : "border-line text-muted hover:border-accent"}`}>
                  {OUTCOME_STYLE[o].label}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label htmlFor="reason"
              className="text-xs uppercase tracking-wide text-muted block mb-1.5">
              Why — this becomes an evaluation case
            </label>
            <textarea id="reason" rows={3} value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="What did the system miss, or get wrong?"
              className="w-full rounded-lg border border-line bg-paper px-3 py-2 text-sm
                         text-ink placeholder:text-muted focus:border-accent focus:outline-none" />
          </div>
          <div className="flex gap-2">
            <button onClick={() => submit(true)}
              disabled={pending || !override || reason.trim().length < 10}
              className="px-4 py-2 rounded-lg bg-accent text-paper text-sm font-semibold
                         disabled:opacity-40 disabled:cursor-not-allowed">
              {pending ? "Recording…" : "Record my decision"}
            </button>
            <button onClick={() => { setMode(null); setError(null); }}
              className="px-3 py-2 rounded-lg text-sm text-muted hover:text-ink">
              Cancel
            </button>
          </div>
        </div>
      )}

      {error && <p className="text-sm text-down">{error}</p>}
    </div>
  );
}
