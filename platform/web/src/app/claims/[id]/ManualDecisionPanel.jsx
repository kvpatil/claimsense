"use client";

import { useState, useTransition } from "react";
import { recordManualDecision } from "./actions";
import { OUTCOME_STYLE } from "@/lib/format";

const OUTCOMES = ["APPROVE", "DENY", "MORE_INFO", "SIU_REFERRAL"];

/**
 * Working a claim BY HAND — the as-is workflow.
 *
 * This is what the portal offered before ClaimSense: a blank form. The
 * adjuster has already read three systems in three tabs, and now has to
 * remember which clause governs, look up its identifier, work out the
 * deductible, and write the letter.
 *
 * Nothing here is made deliberately awkward to flatter the after state. It is
 * simply what an unaided form is: every field empty, every lookup manual, and
 * no check on whether the clause you cited is the one that applies.
 */
export default function ManualDecisionPanel({ claimId, adjusters, suggestedCents }) {
  const [outcome, setOutcome] = useState("");
  const [rationale, setRationale] = useState("");
  const [cited, setCited] = useState("");
  const [amount, setAmount] = useState("");
  const [seat, setSeat] = useState(
    adjusters.find((a) => a.license_number)?.adjuster_id ?? adjusters[0]?.adjuster_id);
  const [error, setError] = useState(null);
  const [pending, start] = useTransition();

  const current = adjusters.find((a) => a.adjuster_id === Number(seat));
  const unlicensed = current && !current.license_number;

  function submit() {
    setError(null);
    const fd = new FormData();
    fd.set("claim_id", claimId);
    fd.set("adjuster_id", seat);
    fd.set("outcome", outcome);
    fd.set("rationale", rationale);
    fd.set("cited_clause_ids", cited);
    if (outcome === "APPROVE") {
      // Dollars in the box, cents on the wire. The conversion happens once,
      // here, because money is integer cents everywhere behind this form.
      const dollars = Number(amount);
      fd.set("settlement_cents", String(Math.round(dollars * 100)));
    }
    start(async () => {
      const res = await recordManualDecision(fd);
      if (res?.error) setError(res.error);
      else { setOutcome(""); setRationale(""); setCited(""); setAmount(""); }
    });
  }

  return (
    <div className="space-y-3">
      <p className="text-sm text-muted">
        No recommendation on file. Read the evidence, find the governing clause
        in the policy corpus, and record your decision.
      </p>

      <div className="flex flex-wrap items-center gap-2 text-sm">
        <label htmlFor="mseat" className="text-muted">Deciding as</label>
        <select id="mseat" value={seat} onChange={(e) => setSeat(e.target.value)}
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
          This seat holds no adjuster licence and may not decide a claim.
        </p>
      )}

      <div>
        <span className="text-xs uppercase tracking-wide text-muted block mb-1.5">
          Outcome
        </span>
        <div className="flex flex-wrap gap-1.5">
          {OUTCOMES.map((o) => (
            <button key={o} onClick={() => setOutcome(o)}
              className={`px-2.5 py-1 rounded-lg border text-sm transition-colors ${
                outcome === o ? "border-accent bg-accent text-paper font-semibold"
                              : "border-line text-muted hover:border-accent"}`}>
              {OUTCOME_STYLE[o].label}
            </button>
          ))}
        </div>
      </div>

      {outcome === "APPROVE" && (
        <div>
          <label htmlFor="amt"
            className="text-xs uppercase tracking-wide text-muted block mb-1.5">
            Payable, net of the deductible
          </label>
          <div className="flex items-center gap-2">
            <span className="text-muted">$</span>
            <input id="amt" inputMode="decimal" value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder={suggestedCents ? (suggestedCents / 100).toFixed(2) : "0.00"}
              className="num w-40 rounded-lg border border-line bg-paper px-3 py-2
                         text-sm text-ink focus:border-accent focus:outline-none" />
            <span className="text-xs text-muted">
              work it out from the limit and deductible above
            </span>
          </div>
        </div>
      )}

      <div>
        <label htmlFor="cites"
          className="text-xs uppercase tracking-wide text-muted block mb-1.5">
          Clauses relied on
        </label>
        <input id="cites" value={cited} onChange={(e) => setCited(e.target.value)}
          placeholder="e.g. HO3-I-EXCL-3"
          className="num w-full rounded-lg border border-line bg-paper px-3 py-2
                     text-sm text-ink placeholder:text-muted focus:border-accent
                     focus:outline-none" />
        <p className="text-xs text-muted mt-1">
          Typed from memory or looked up in the policy corpus. Nothing checks
          that the clause you name is the one that applies.
        </p>
      </div>

      <div>
        <label htmlFor="mrat"
          className="text-xs uppercase tracking-wide text-muted block mb-1.5">
          Rationale — goes to the claimant
        </label>
        <textarea id="mrat" rows={4} value={rationale}
          onChange={(e) => setRationale(e.target.value)}
          placeholder="Why this outcome, in words the claimant will read."
          className="w-full rounded-lg border border-line bg-paper px-3 py-2 text-sm
                     text-ink placeholder:text-muted focus:border-accent focus:outline-none" />
      </div>

      <button onClick={submit}
        disabled={pending || unlicensed || !outcome || rationale.trim().length < 20}
        className="px-4 py-2 rounded-lg bg-accent text-paper text-sm font-semibold
                   disabled:opacity-40 disabled:cursor-not-allowed hover:opacity-90">
        {pending ? "Recording…" : "Record my decision"}
      </button>

      {error && <p className="text-sm text-down">{error}</p>}
    </div>
  );
}
