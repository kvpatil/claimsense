import Link from "next/link";
import { Page, Crumb } from "@/components/Chrome";
import { OutcomeBadge, SourceBadge, ConfirmBadge } from "@/components/Badges";
import { listClaims } from "@/lib/queries";
import { usd, shortDate } from "@/lib/format";

export const dynamic = "force-dynamic";

const FILTERS = [
  { key: "", label: "All" },
  { key: "APPROVE", label: "Approve" },
  { key: "DENY", label: "Deny" },
  { key: "MORE_INFO", label: "More info" },
  { key: "SIU_REFERRAL", label: "SIU" },
];

export default async function ClaimsQueue({ searchParams }) {
  const outcome = searchParams?.outcome || null;
  const claims = await listClaims({ limit: 300, outcome });

  return (
    <Page current="/claims">
      <Crumb items={[{ label: "Claims" }]} />
      <div className="flex flex-wrap items-end justify-between gap-4 mb-5">
        <div>
          <h1 className="text-2xl mb-1">Claim queue</h1>
          <p className="text-muted text-sm">
            {claims.length} claim{claims.length === 1 ? "" : "s"}
            {outcome ? ` recommended ${outcome.replace("_", " ").toLowerCase()}` : ""}.
            Open one to see the evidence, the clauses it turns on, and the draft decision.
          </p>
        </div>
        <nav className="flex gap-1.5 flex-wrap">
          {FILTERS.map((f) => {
            const active = (outcome ?? "") === f.key;
            return (
              <Link key={f.key}
                href={f.key ? `/claims?outcome=${f.key}` : "/claims"}
                className={`px-2.5 py-1 rounded-lg text-sm border transition-colors ${
                  active ? "border-accent bg-accent text-paper font-semibold"
                         : "border-line text-muted hover:border-accent hover:text-accent"}`}>
                {f.label}
              </Link>
            );
          })}
        </nav>
      </div>

      {/* The table scrolls inside its own box. A claims table is the first
          thing that would make the whole page scroll sideways. */}
      <div className="card scroll-x">
        <table className="w-full text-sm min-w-[1000px]">
          <thead>
            <tr className="text-left text-xs uppercase tracking-wide text-muted
                           border-b border-line">
              <Th className="pl-5">Claim</Th>
              <Th>Peril</Th>
              <Th>Form</Th>
              <Th>Date of loss</Th>
              <Th className="text-right">Claimed</Th>
              <Th>Recommendation</Th>
              <Th>Basis</Th>
              <Th className="pr-5">Status</Th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {claims.map((c) => (
              <tr key={c.claim_id} className="hover:bg-tint/60 group">
                <td className="pl-5 py-2.5">
                  <Link href={`/claims/${c.claim_id}`}
                        className="num font-medium text-accent group-hover:underline">
                    {c.claim_number}
                  </Link>
                  <div className="text-xs text-muted">{c.adjuster ?? "unassigned"}</div>
                </td>
                <td className="py-2.5 capitalize">{c.peril}</td>
                <td className="py-2.5">
                  <span className="num text-xs">{c.product ?? "—"}</span>
                  {c.policy_status && c.policy_status !== "active" && (
                    <span className="ml-1.5 chip border-down text-down !px-1.5 !py-0">
                      {c.policy_status}
                    </span>
                  )}
                </td>
                <td className="py-2.5 num text-muted">{shortDate(c.date_of_loss)}</td>
                <td className="py-2.5 num text-right">
                  {usd(Number(c.claimed_amount_cents))}
                  {c.settlement_cents != null && (
                    <div className="text-xs text-up">
                      settle {usd(Number(c.settlement_cents))}
                    </div>
                  )}
                </td>
                <td className="py-2.5"><OutcomeBadge outcome={c.outcome} /></td>
                <td className="py-2.5"><SourceBadge source={c.source} /></td>
                <td className="py-2.5 pr-5">
                  {c.outcome
                    ? <ConfirmBadge confirmedAt={c.confirmed_at}
                                    overrideOutcome={c.override_outcome} />
                    : <span className="text-xs text-muted">not worked</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {claims.length === 0 && (
          <p className="text-center text-muted text-sm py-10">
            No claims match that filter.
          </p>
        )}
      </div>
    </Page>
  );
}

function Th({ children, className = "" }) {
  return <th className={`py-2.5 font-medium ${className}`}>{children}</th>;
}
