import Link from "next/link";
import { Page, Panel } from "@/components/Chrome";
import { OutcomeBadge } from "@/components/Badges";
import { listClaims, queueStats } from "@/lib/queries";
import { usd } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function Overview() {
  const [{ rows, total }, claims] = await Promise.all([
    queueStats(), listClaims({ limit: 500 }),
  ]);

  const triaged = rows.filter((r) => r.outcome !== "UNTRIAGED");
  const done = triaged.reduce((s, r) => s + r.n, 0);
  const confirmed = triaged.reduce((s, r) => s + r.confirmed, 0);
  const exposure = claims
    .filter((c) => !c.outcome || c.outcome === "APPROVE")
    .reduce((s, c) => s + Number(c.claimed_amount_cents), 0);

  return (
    <Page current="/">
      <div className="mb-6">
        <h1 className="text-2xl mb-1">Claims overview</h1>
        <p className="text-muted">
          ClaimSense reads each claim across the three systems, checks coverage
          against the policy corpus, and drafts a first decision. A licensed
          adjuster confirms every outcome.
        </p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <Stat label="Claims in queue" value={total} />
        <Stat label="First decision drafted" value={done}
              note={`${total - done} not yet worked`} />
        <Stat label="Confirmed by an adjuster" value={confirmed}
              note={done ? `${Math.round((confirmed / done) * 100)}% of drafted` : "—"} />
        <Stat label="Open exposure" value={usd(exposure)}
              note="claimed, not yet denied" />
      </div>

      <div className="grid lg:grid-cols-[1fr_380px] gap-5">
        <Panel title="Recommendations by outcome"
               sub="Every one of these is awaiting or has received human confirmation.">
          <div className="space-y-2.5">
            {rows.map((r) => {
              const pct = total ? (r.n / total) * 100 : 0;
              return (
                <div key={r.outcome} className="flex items-center gap-3">
                  <div className="w-36 shrink-0">
                    <OutcomeBadge outcome={r.outcome === "UNTRIAGED" ? null : r.outcome} />
                  </div>
                  <div className="flex-1 h-2 rounded-full bg-note overflow-hidden">
                    <div className="h-full rounded-full bg-accent"
                         style={{ width: `${pct}%` }} />
                  </div>
                  <span className="num text-sm w-10 text-right">{r.n}</span>
                  <span className="num text-xs text-muted w-24 text-right">
                    {r.confirmed} confirmed
                  </span>
                </div>
              );
            })}
          </div>
        </Panel>

        <Panel title="How a decision is made"
               sub="What is arithmetic and what is judgment.">
          <dl className="space-y-3 text-sm">
            <Split k="Deterministic code"
                   v="Identity and access, the fair-claims clock, whether cover
                      was in force, the deductible and limit arithmetic, the
                      fraud score." />
            <Split k="Model judgment"
                   v="Reading the file, interpreting which clause governs,
                      weighing the fraud indicators, drafting the decision." />
            <Split k="Always"
                   v="Every coverage conclusion cites the clauses actually
                      retrieved. A conclusion that cannot cite one is blocked,
                      not returned." />
          </dl>
        </Panel>
      </div>

      <div className="mt-5">
        <Panel title="Needs an adjuster"
               sub="Drafted, not yet confirmed — the queue a human works."
               right={<Link href="/claims" className="text-sm text-accent hover:underline">
                        All claims →</Link>}>
          <ul className="divide-y divide-line -my-1">
            {claims.filter((c) => c.outcome && !c.confirmed_at).slice(0, 8).map((c) => (
              <li key={c.claim_id}>
                <Link href={`/claims/${c.claim_id}`}
                      className="flex items-center gap-3 py-2.5 hover:bg-tint -mx-2 px-2 rounded-lg">
                  <span className="num text-sm text-muted w-16">{c.claim_id}</span>
                  <span className="text-sm w-24 capitalize">{c.peril}</span>
                  <span className="num text-sm w-28 text-right">
                    {usd(Number(c.claimed_amount_cents))}
                  </span>
                  <span className="flex-1" />
                  <OutcomeBadge outcome={c.outcome} />
                </Link>
              </li>
            ))}
            {claims.filter((c) => c.outcome && !c.confirmed_at).length === 0 && (
              <li className="py-6 text-center text-muted text-sm">
                Nothing drafted yet. Run <code className="px-1.5 py-0.5 rounded
                bg-note text-ink">make agent</code> to work a claim.
              </li>
            )}
          </ul>
        </Panel>
      </div>
    </Page>
  );
}

function Stat({ label, value, note }) {
  return (
    <div className="card px-4 py-3">
      <div className="text-xs text-muted uppercase tracking-wide">{label}</div>
      <div className="num text-2xl font-semibold mt-1 leading-none">{value}</div>
      {note && <div className="text-xs text-muted mt-1.5">{note}</div>}
    </div>
  );
}

function Split({ k, v }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-accent mb-0.5">{k}</dt>
      <dd className="text-muted leading-relaxed">{v}</dd>
    </div>
  );
}
