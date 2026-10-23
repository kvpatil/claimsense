import { Page, Crumb, Panel } from "@/components/Chrome";
import { query } from "@/lib/db";
import { recentRuns } from "@/lib/queries";
import { shortDate } from "@/lib/format";

export const dynamic = "force-dynamic";

/** The engineering view: what the system did, and what it refused to do. */
export default async function Internals() {
  const [runs, audit, denials] = await Promise.all([
    recentRuns(12),
    query(`SELECT audit_id, adjuster_id::int, system, action, decision,
                  COALESCE(reason,'') AS reason, created_at
             FROM platform.audit_log ORDER BY audit_id DESC LIMIT 25`),
    query(`SELECT count(*)::int AS n FROM platform.audit_log WHERE decision='deny'`),
  ]);

  return (
    <Page current="/internals">
      <Crumb items={[{ label: "Internals" }]} />
      <h1 className="text-2xl mb-1">Internals</h1>
      <p className="text-muted text-sm mb-5 max-w-[75ch]">
        The audit trail and the pipeline runs behind it. Denials are recorded as
        carefully as successes — &ldquo;who tried to read what and was
        stopped&rdquo; is the question an audit actually asks.
      </p>

      <div className="grid lg:grid-cols-2 gap-5">
        <Panel title="Pipeline runs"
               sub="One row per claim the agent worked, with the guardrails that fired.">
          {runs.length === 0 ? (
            <p className="text-sm text-muted">
              No runs recorded yet. <code className="px-1.5 py-0.5 rounded bg-note
              text-ink num">make agent</code> writes one per claim worked.
            </p>
          ) : (
            <div className="scroll-x">
              <table className="w-full text-sm min-w-[520px]">
                <thead className="text-xs uppercase tracking-wide text-muted">
                  <tr className="border-b border-line text-left">
                    <th className="py-2 font-medium">Claim</th>
                    <th className="py-2 font-medium">Outcome</th>
                    <th className="py-2 font-medium">Brain</th>
                    <th className="py-2 font-medium text-right">ms</th>
                    <th className="py-2 font-medium">Guardrails</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {runs.map((r) => (
                    <tr key={r.run_id}>
                      <td className="py-2 num">{r.claim_id}</td>
                      <td className="py-2">{r.outcome ?? "—"}</td>
                      <td className="py-2 text-muted">{r.brain}</td>
                      <td className="py-2 num text-right text-muted">{r.duration_ms}</td>
                      <td className="py-2 text-xs text-muted">
                        {r.guardrails_fired?.join(", ") || "none fired"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>

        <Panel title="Audit log"
               sub={`${denials[0]?.n ?? 0} denials recorded.`}>
          <div className="scroll-x">
            <table className="w-full text-sm min-w-[520px]">
              <thead className="text-xs uppercase tracking-wide text-muted">
                <tr className="border-b border-line text-left">
                  <th className="py-2 font-medium">Seat</th>
                  <th className="py-2 font-medium">System</th>
                  <th className="py-2 font-medium">Action</th>
                  <th className="py-2 font-medium">Result</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {audit.map((a) => (
                  <tr key={a.audit_id}>
                    <td className="py-2 num text-muted">{a.adjuster_id ?? "—"}</td>
                    <td className="py-2 uppercase text-xs">{a.system}</td>
                    <td className="py-2">{a.action}</td>
                    <td className="py-2">
                      {a.decision === "deny" ? (
                        <span className="text-down text-xs">
                          denied — {a.reason}
                        </span>
                      ) : <span className="text-up text-xs">allowed</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {audit.length === 0 && (
            <p className="text-sm text-muted">Nothing recorded yet.</p>
          )}
        </Panel>
      </div>
    </Page>
  );
}
