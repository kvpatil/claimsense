import { OUTCOME_STYLE } from "@/lib/format";

/** The four outcomes.
 *
 * Colour is never the only signal — every badge carries its label, so the
 * screen reads identically to a colour-blind adjuster. The dot is redundant
 * reinforcement, not the message.
 */
export function OutcomeBadge({ outcome, className = "" }) {
  if (!outcome) {
    return <span className={`chip ${className}`}>Untriaged</span>;
  }
  const s = OUTCOME_STYLE[outcome] ?? { label: outcome, cls: "" };
  return (
    <span className={`chip ${s.cls} font-semibold ${className}`}>
      <span className="h-1.5 w-1.5 rounded-full bg-current" aria-hidden />
      {s.label}
    </span>
  );
}

/** Model vs deterministic fallback — the M2 requirement, on screen.
 *
 * These must never look like the same kind of output. A verdict a model
 * reasoned to and one a date comparison substituted carry different weight for
 * the adjuster deciding whether to trust it, so they are rendered differently
 * and labelled in words.
 */
export function SourceBadge({ source }) {
  if (!source) return null;
  const model = source === "model";
  return (
    <span className={`chip font-medium ${model
      ? "border-line text-muted" : "border-accent text-accent bg-tint"}`}>
      {model ? "model judgment" : "deterministic fallback"}
    </span>
  );
}

export function ConfirmBadge({ confirmedAt, overrideOutcome }) {
  if (!confirmedAt) {
    return <span className="chip border-warn text-warn font-medium">
      Awaiting adjuster
    </span>;
  }
  if (overrideOutcome) {
    return <span className="chip border-down text-down font-medium">
      Overridden → {OUTCOME_STYLE[overrideOutcome]?.label ?? overrideOutcome}
    </span>;
  }
  return <span className="chip border-up text-up font-medium">Confirmed</span>;
}
