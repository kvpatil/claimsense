/** Who the client is, and what their system is called.
 *
 * THE PORTAL IS THE CLIENT'S. Northwind Mutual has been adjudicating claims on
 * Claims Desk for years; it is the system their adjusters already live in, and
 * in Week 1 it contains no AI of any kind.
 *
 * ClaimSense is OURS — the automated workflow the engagement puts behind that
 * desk. It does not advise the adjuster; it DOES the work the adjuster used to
 * do, and surfaces a finished decision for confirmation. Keeping the two names
 * apart in code is what stops the demo quietly claiming we built the client's
 * portal.
 *
 * Synthetic. Northwind Mutual is not a real insurer.
 */
export const CLIENT = {
  name: "Northwind Mutual",
  short: "Northwind",
  system: "Claims Desk",
  // Their colour, not ours. The deep slate-teal is the client's existing house
  // style; ClaimSense's violet marks the surfaces the automation produced, so
  // on the integrated screen you can see at a glance which work was theirs and
  // which was ours.
  mark: "#1f4d52",
};

export const VENDOR = {
  product: "ClaimSense",
  // What it does, in the client's terms. Not "assists with" — it works the
  // claim end to end and stops at the one step the law reserves for a person.
  tagline: "Adjudication, automated · confirmed by a licensed adjuster",
};
