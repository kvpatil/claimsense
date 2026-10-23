/** Display helpers. The ONE place cents become a decimal. */

// Money crosses the wire as integer cents and is formatted exactly once, here.
// Every other module treats it as an integer, which is what keeps settlement
// arithmetic exact.
export function usd(cents) {
  if (cents === null || cents === undefined) return "—";
  return (cents / 100).toLocaleString("en-US", {
    style: "currency", currency: "USD", maximumFractionDigits: 2,
  });
}

export function shortDate(value) {
  if (!value) return "—";
  return new Date(value).toLocaleDateString("en-US", {
    year: "numeric", month: "short", day: "numeric",
  });
}

export function titleCase(s) {
  return String(s || "").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

// The four outcomes, with the colour each wears. Colour is never the only
// signal — every badge carries its label too, so a colour-blind adjuster reads
// the same thing a colour-sighted one does.
export const OUTCOME_STYLE = {
  APPROVE:      { label: "Approve",      cls: "border-up text-up" },
  DENY:         { label: "Deny",         cls: "border-down text-down" },
  MORE_INFO:    { label: "More info",    cls: "border-warn text-warn" },
  SIU_REFERRAL: { label: "SIU referral", cls: "border-accent text-accent" },
};
