import { Page, Crumb, Panel } from "@/components/Chrome";
import { query } from "@/lib/db";

export const dynamic = "force-dynamic";

const TYPE_TONE = {
  grant: "border-up text-up",
  exclusion: "border-down text-down",
  condition: "border-line text-muted",
  definition: "border-line text-muted",
  limit: "border-warn text-warn",
};

export default async function PolicyCorpus({ searchParams }) {
  const product = searchParams?.product || null;
  const clauses = await query(
    `SELECT clause_id, product, section, title, clause_type, body, perils
       FROM pas.policy_clauses
      ${product ? "WHERE product = $1" : ""}
      ORDER BY product, clause_id`,
    product ? [product] : []);

  const products = ["HO3", "HO4", "AUTO", "ALL"];

  return (
    <Page current="/policy">
      <Crumb items={[{ label: "Policy corpus" }]} />
      <div className="flex flex-wrap items-end justify-between gap-4 mb-5">
        <div>
          <h1 className="text-2xl mb-1">Policy corpus</h1>
          <p className="text-muted text-sm max-w-[70ch]">
            The clauses coverage decisions are retrieved from and cited against.
            Every citation in a recommendation points at one of these, and a
            conclusion citing an identifier that was never retrieved is blocked
            rather than returned.
          </p>
        </div>
        <nav className="flex gap-1.5">
          {[{ k: "", l: "All" }, ...products.map((p) => ({ k: p, l: p }))].map((f) => {
            const active = (product ?? "") === f.k;
            return (
              <a key={f.k} href={f.k ? `/policy?product=${f.k}` : "/policy"}
                className={`px-2.5 py-1 rounded-lg text-sm border transition-colors ${
                  active ? "border-accent bg-accent text-paper font-semibold"
                         : "border-line text-muted hover:border-accent hover:text-accent"}`}>
                {f.l}
              </a>
            );
          })}
        </nav>
      </div>

      <Panel title={`${clauses.length} clauses`}
             sub="Synthetic wording modelled on an ISO-style form. Not any insurer's actual policy.">
        <div className="grid md:grid-cols-2 gap-3">
          {clauses.map((c) => (
            <article key={c.clause_id} className="rounded-lg border border-line p-3.5">
              <div className="flex items-baseline justify-between gap-2 mb-1.5">
                <code className="num text-xs font-semibold text-accent">{c.clause_id}</code>
                <span className={`chip !py-0 !px-1.5 capitalize ${TYPE_TONE[c.clause_type]}`}>
                  {c.clause_type}
                </span>
              </div>
              <h3 className="text-sm font-semibold mb-1">{c.title}</h3>
              <p className="text-sm text-muted leading-relaxed">{c.body}</p>
              {c.perils?.length > 0 && (
                <p className="text-xs text-muted/70 mt-2">
                  Perils: {c.perils.join(", ")}
                </p>
              )}
            </article>
          ))}
        </div>
      </Panel>
    </Page>
  );
}
