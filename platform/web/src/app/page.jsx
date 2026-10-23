import Link from "next/link";
import { Page, Panel } from "@/components/Chrome";
import { OutcomeBadge } from "@/components/Badges";
import { listClaims, queueStats } from "@/lib/queries";
import { usd } from "@/lib/format";
import { CLIENT, VENDOR } from "@/lib/client";

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
        <p className="text-muted max-w-[80ch]">
          {done === 0 ? (
            <>Every claim below is adjudicated by hand. An adjuster opens the
            file, reads the policy in the administration system, checks the
            documents, finds the governing clause, works out the deductible,
            and writes the decision.</>
          ) : (
            <>{VENDOR.product} has worked {done} of these end to end — read the
            file across all three systems, established cover, applied the policy
            wording and produced the decision. A licensed adjuster confirms
            every outcome before it reaches a claimant.</>
          )}
        </p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <Stat label="Claims in queue" value={total} />
        <Stat label={done === 0 ? "Worked" : "First decision drafted"} value={done}
              note={`${total - done} not yet worked`} />
        <Stat label="Decided by an adjuster" value={confirmed}
              note={done ? `${Math.round((confirmed / done) * 100)}% of worked` : "—"} />
        <Stat label="Open exposure" value={usd(exposure)}
              note="claimed, not yet denied" />
      </div>

      <div className="grid lg:grid-cols-[1fr_380px] gap-5">
        <Panel title={done === 0 ? "Queue by status" : "Decisions by outcome"}
               sub={done === 0
                 ? "Nothing has been worked yet. This is the backlog as it stands."
                 : "Every one of these is awaiting or has received human confirmation."}>
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

        {done === 0 ? (
          <Panel title="How a claim is worked today"
                 sub="The current process, end to end.">
            <ol className="space-y-3 text-sm list-decimal list-inside text-muted">
              <li><span className="text-ink">Open the claim</span> in Claims
                  Desk and read the first notice of loss.</li>
              <li><span className="text-ink">Switch to policy administration</span>
                  to check the policy was in force on the date of loss, and find
                  the limit and deductible.</li>
              <li><span className="text-ink">Switch to the document store</span>
                  to see what has been supplied and what is missing.</li>
              <li><span className="text-ink">Find the governing clause</span> in
                  the policy wording, from memory or by searching the form.</li>
              <li><span className="text-ink">Work out what is payable</span> and
                  write the decision letter.</li>
            </ol>
            <p className="text-xs text-muted mt-3 pt-3 border-t border-line">
              Three systems, three tabs, and no two adjusters reach the clause
              the same way.
            </p>
          </Panel>
        ) : (
          <Panel title="How a decision is made" vendor
                 sub={`What ${VENDOR.product} computes and what it interprets.`}>
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
        )}
      </div>

      <div className="mt-5">
        <Panel title={done === 0 ? "Oldest unworked claims" : "Needs an adjuster"}
               sub={done === 0
                 ? "Ordered as the queue presents them."
                 : "Drafted, not yet confirmed — the queue a human works."}
               right={<Link href="/claims" className="text-sm text-accent hover:underline">
                        All claims →</Link>}>
          <ul className="divide-y divide-line -my-1">
            {(done === 0
                ? claims.filter((c) => !c.outcome).slice(0, 8)
                : claims.filter((c) => c.outcome && !c.confirmed_at).slice(0, 8)
             ).map((c) => (
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
            {done > 0 && claims.filter((c) => c.outcome && !c.confirmed_at).length === 0 && (
              <li className="py-6 text-center text-muted text-sm">
                Every drafted decision has been confirmed.
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
