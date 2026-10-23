import { notFound } from "next/navigation";
import { Page, Crumb, Panel } from "@/components/Chrome";
import { OutcomeBadge, SourceBadge, ConfirmBadge } from "@/components/Badges";
import { getAdjusters, getClaimBundle, getClauses } from "@/lib/queries";
import { usd, shortDate, titleCase } from "@/lib/format";
import { VENDOR } from "@/lib/client";
import ConfirmPanel from "./ConfirmPanel";
import ManualDecisionPanel from "./ManualDecisionPanel";

export const dynamic = "force-dynamic";

export default async function Workbench({ params }) {
  const bundle = await getClaimBundle(params.id);
  if (!bundle) notFound();

  const { claim, policy, insured, coverages, fnol, notes, signals,
          documents, decisions } = bundle;
  const latest = decisions[0] ?? null;
  const [clauses, adjusters] = await Promise.all([
    getClauses(latest?.cited_clause_ids ?? []),
    getAdjusters(),
  ]);

  const quarantined = documents.filter((d) => d.is_poisoned);
  const usable = documents.filter((d) => !d.is_poisoned);
  const fraudScore = signals.reduce((s, x) => s + x.weight, 0);

  return (
    <Page current="/claims">
      <Crumb items={[{ label: "Claims", href: "/claims" },
                     { label: claim.claim_number }]} />

      <header className="flex flex-wrap items-start justify-between gap-4 mb-5">
        <div>
          <h1 className="text-2xl mb-1 capitalize">
            {claim.peril} loss · {usd(Number(claim.claimed_amount_cents))}
          </h1>
          <p className="text-muted text-sm">
            {insured?.full_name} · loss {shortDate(claim.date_of_loss)} ·
            reported {shortDate(claim.reported_at)} · {claim.loss_state}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {latest && <OutcomeBadge outcome={latest.override_outcome ?? latest.outcome} />}
          {latest && <SourceBadge source={latest.source} />}
          {latest && <ConfirmBadge confirmedAt={latest.confirmed_at}
                                   overrideOutcome={latest.override_outcome} />}
        </div>
      </header>

      <div className="grid xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_380px] gap-5">

        {/* ---------- EVIDENCE: what was read, labelled by source system ---- */}
        <div className="space-y-5">
          <Panel title="Evidence" sub="Gathered across the three client systems.">
            <Source name="Claims management">
              <Row k="Claim" v={claim.claim_number} />
              <Row k="Status" v={titleCase(claim.status)} />
              <Row k="Adjuster" v={claim.adjuster_name ?? "unassigned"} />
            </Source>

            <Source name="Policy administration" missing={!policy}>
              {policy ? (
                <>
                  <Row k="Policy" v={`${policy.policy_number} (${policy.product})`} />
                  <Row k="In force" v={`${policy.effective_date} → ${policy.expiration_date}`} />
                  <Row k="Status" v={titleCase(policy.status)}
                       tone={policy.status !== "active" ? "down" : null} />
                  {policy.lapse_date && (
                    <Row k="Lapsed" v={policy.lapse_date} tone="down" />
                  )}
                </>
              ) : (
                <p className="text-sm text-down">
                  Policy {claim.policy_id} returned no record. The claim carries a
                  reference the policy system does not resolve, so coverage cannot
                  be assessed against any form.
                </p>
              )}
            </Source>

            <Source name="Document store">
              {usable.length === 0 && (
                <p className="text-sm text-muted">Nothing usable on file.</p>
              )}
              <ul className="space-y-1">
                {usable.map((d) => (
                  <li key={d.document_id} className="text-sm flex items-baseline gap-2">
                    <span className="text-accent">·</span>
                    <span>{titleCase(d.doc_type)}</span>
                    <span className="num text-xs text-muted">
                      {d.page_count}p · {shortDate(d.uploaded_at)}
                    </span>
                  </li>
                ))}
              </ul>
              {quarantined.length > 0 && (
                /* The quarantine is SHOWN, never silent. An adjuster has to
                   know a document was withheld and why — both because it is
                   evidence about the claim and because it explains why the
                   file may now be incomplete. */
                <div className="mt-3 rounded-lg border border-down/50 bg-down/5 px-3 py-2.5">
                  <p className="text-sm font-semibold text-down mb-1">
                    {quarantined.length} document withheld
                  </p>
                  <ul className="text-sm text-muted space-y-0.5">
                    {quarantined.map((d) => (
                      <li key={d.document_id}>
                        {titleCase(d.doc_type)} ({d.filename}) carried text
                        addressed to an automated reader. It was not given to the
                        model, and it does not count towards a complete file.
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </Source>
          </Panel>

          <Panel title="First notice of loss"
                 sub="The claimant's own account — attacker-influenceable, read as evidence.">
            {fnol.map((f) => (
              <blockquote key={f.fnol_id}
                className="text-sm leading-relaxed border-l-2 border-accent pl-3 text-ink">
                {f.narrative}
                <footer className="text-xs text-muted mt-2 not-italic">
                  {titleCase(f.reported_by)} via {f.channel} · {shortDate(f.recorded_at)}
                </footer>
              </blockquote>
            ))}
            {notes.length > 0 && (
              <div className="mt-4 pt-3 border-t border-line space-y-2">
                {notes.map((n) => (
                  <p key={n.note_id} className="text-sm text-muted">
                    <span className="text-xs">{shortDate(n.created_at)}</span> — {n.body}
                  </p>
                ))}
              </div>
            )}
          </Panel>
        </div>

        {/* ---------- COVERAGE: the clauses, with their actual text --------- */}
        <div className="space-y-5">
          <Panel title="Policy clauses relied on" tone="judgment"
                 sub="The text, not just the identifier — so the citation can be checked.">
            {clauses.length === 0 ? (
              <p className="text-sm text-muted">
                {latest ? "This outcome rests on a deterministic check rather than "
                        + "a reading of the policy form, so it cites no clause."
                        : "No recommendation yet."}
              </p>
            ) : (
              <div className="space-y-3">
                {clauses.map((c) => (
                  <article key={c.clause_id}
                    className="rounded-lg border border-line bg-note px-3.5 py-3">
                    <div className="flex items-baseline justify-between gap-3 mb-1.5">
                      <code className="num text-xs font-semibold text-accent">
                        {c.clause_id}
                      </code>
                      <span className="chip !py-0 !px-1.5 capitalize">{c.clause_type}</span>
                    </div>
                    <h3 className="text-sm font-semibold mb-1">{c.title}</h3>
                    <p className="text-sm text-muted leading-relaxed">{c.body}</p>
                    <p className="text-xs text-muted/70 mt-1.5">{c.section}</p>
                  </article>
                ))}
              </div>
            )}
          </Panel>

          <Panel title="Fraud indicators" tone="code"
                 sub={`Score ${fraudScore} — the sum is arithmetic; what it means is not.`}>
            {signals.length === 0 ? (
              <p className="text-sm text-muted">
                No indicators recorded against this claim.
              </p>
            ) : (
              <ul className="space-y-2">
                {signals.map((s) => (
                  <li key={s.indicator_code} className="text-sm">
                    <div className="flex items-baseline gap-2">
                      <code className="num text-xs text-accent">{s.indicator_code}</code>
                      <span className="num text-xs text-muted">+{s.weight}</span>
                    </div>
                    <p className="text-muted">{s.detail}</p>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </div>

        {/* ---------- DECISION ---------------------------------------------- */}
        <div className="space-y-5">
          <Panel title="Cover and money" tone="code"
                 sub="Dates and arithmetic. No model runs here.">
            {coverages.length === 0 ? (
              <p className="text-sm text-muted">No coverages — the policy did not resolve.</p>
            ) : (
              <table className="w-full text-sm">
                <tbody className="divide-y divide-line">
                  {coverages.map((c) => (
                    <tr key={c.coverage_code}>
                      <td className="py-1.5 font-medium">{c.coverage_code}</td>
                      <td className="py-1.5 num text-right text-muted">
                        {usd(Number(c.limit_cents))}
                      </td>
                      <td className="py-1.5 num text-right text-muted text-xs">
                        −{usd(Number(c.deductible_cents))}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Panel>

          <Panel title="First decision"
                 sub={latest ? `Produced by ${VENDOR.product}. Not yet a decision.`
                             : "Worked by hand — the as-is workflow."}>
            {!latest ? (
              /* No recommendation on file. This is the Week 1 state and the
                 portal's original capability: the adjuster decides unaided. */
              <ManualDecisionPanel
                claimId={claim.claim_id}
                adjusters={adjusters}
                suggestedCents={null} />
            ) : (
              <div className="space-y-4">
                <div className="flex flex-wrap items-center gap-2">
                  <OutcomeBadge outcome={latest.outcome} />
                  <SourceBadge source={latest.source} />
                  {latest.confidence != null && (
                    <span className="chip num">
                      confidence {Number(latest.confidence).toFixed(2)}
                    </span>
                  )}
                </div>

                {latest.settlement_cents != null && (
                  <div className="rounded-lg bg-note px-3.5 py-2.5">
                    <div className="text-xs uppercase tracking-wide text-muted">
                      Payable, net of deductible
                    </div>
                    <div className="num text-xl font-semibold text-up">
                      {usd(Number(latest.settlement_cents))}
                    </div>
                  </div>
                )}

                <p className="text-sm leading-relaxed">{latest.rationale}</p>

                {latest.cited_clause_ids?.length > 0 && (
                  <p className="text-xs text-muted">
                    Cites {latest.cited_clause_ids.join(", ")} — each retrieved
                    from the policy corpus, shown in full alongside.
                  </p>
                )}

                <div className="pt-3 border-t border-line">
                  <ConfirmPanel decision={latest} adjusters={adjusters} />
                </div>
              </div>
            )}
          </Panel>

          {decisions.length > 1 && (
            <Panel title="Earlier recommendations">
              <ul className="space-y-2 text-sm">
                {decisions.slice(1).map((d) => (
                  <li key={d.decision_id} className="flex items-center gap-2">
                    <OutcomeBadge outcome={d.outcome} />
                    <span className="text-xs text-muted">{shortDate(d.created_at)}</span>
                  </li>
                ))}
              </ul>
            </Panel>
          )}
        </div>
      </div>
    </Page>
  );
}

function Source({ name, children, missing }) {
  return (
    <div className="mb-4 last:mb-0">
      <div className="flex items-center gap-2 mb-1.5">
        <span className={`h-1.5 w-1.5 rounded-full ${missing ? "bg-down" : "bg-up"}`} />
        <span className="text-xs uppercase tracking-wide text-muted">{name}</span>
      </div>
      <div className="pl-3.5">{children}</div>
    </div>
  );
}

function Row({ k, v, tone }) {
  return (
    <div className="flex items-baseline justify-between gap-3 text-sm py-0.5">
      <span className="text-muted">{k}</span>
      <span className={`num text-right ${tone === "down" ? "text-down font-medium" : ""}`}>
        {v}
      </span>
    </div>
  );
}
