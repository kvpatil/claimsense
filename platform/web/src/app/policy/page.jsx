import { Page, Crumb, Panel } from "@/components/Chrome";
import { query } from "@/lib/db";
import { CLIENT } from "@/lib/client";

export const dynamic = "force-dynamic";

const TYPE_TONE = {
  grant: "border-up text-up",
  exclusion: "border-down text-down",
  condition: "border-line text-muted",
  definition: "border-line text-muted",
  limit: "border-warn text-warn",
};

/**
 * The policy wording, as an adjuster searches it BY HAND.
 *
 * This is the Week 1 capability and the manual counterpart of the
 * `search_policy_clauses` tool the agent gets in Week 3. The difference is
 * worth seeing side by side:
 *
 *   here   the adjuster types words they hope appear in the form, reads what
 *          comes back, and decides which clause governs. Nothing ranks by
 *          relevance to a claim, nothing knows the peril, and whether the
 *          right clause surfaces depends on choosing the insurer's vocabulary
 *          rather than the claimant's.
 *
 *   agent  the same corpus, pre-filtered by product and peril, ranked by BM25
 *          against the claim's own narrative, and the ids it returns are
 *          recorded — so a citation can be checked against what was actually
 *          retrieved.
 *
 * Deliberately a plain substring match. Making it clever would flatter the
 * before state and hide the thing the engagement is about.
 */
export default async function PolicyWording({ searchParams }) {
  const product = searchParams?.product || null;
  const q = (searchParams?.q || "").trim();

  const where = [];
  const params = [];
  if (product) { params.push(product); where.push(`product = $${params.length}`); }
  if (q) {
    params.push(`%${q}%`);
    const i = params.length;
    where.push(`(body ILIKE $${i} OR title ILIKE $${i} OR clause_id ILIKE $${i})`);
  }

  const clauses = await query(
    `SELECT clause_id, product, section, title, clause_type, body, perils
       FROM pas.policy_clauses
      ${where.length ? "WHERE " + where.join(" AND ") : ""}
      ORDER BY product, clause_id`, params);

  const total = await query(`SELECT count(*)::int AS n FROM pas.policy_clauses`);

  return (
    <Page current="/policy">
      <Crumb items={[{ label: "Policy wording" }]} />
      <div className="mb-5">
        <h1 className="text-2xl mb-1">Policy wording</h1>
        <p className="text-muted text-sm max-w-[78ch]">
          The forms {CLIENT.name} writes on. Search the wording to find the
          clause that governs a loss — this is the reference an adjuster works
          from when deciding a claim.
        </p>
      </div>

      {/* A plain GET form. No JS, because the legacy system has none. */}
      <form className="card px-5 py-4 mb-5" method="get">
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex-1 min-w-[260px]">
            <label htmlFor="q"
              className="text-xs uppercase tracking-wide text-muted block mb-1.5">
              Search the wording
            </label>
            <input id="q" name="q" defaultValue={q}
              placeholder="e.g. water damage, vacant, deductible"
              className="w-full rounded-lg border border-line bg-note px-3 py-2
                         text-sm text-ink placeholder:text-muted
                         focus:border-accent focus:outline-none" />
          </div>
          <div>
            <label htmlFor="product"
              className="text-xs uppercase tracking-wide text-muted block mb-1.5">
              Form
            </label>
            <select id="product" name="product" defaultValue={product ?? ""}
              className="rounded-lg border border-line bg-note px-3 py-2 text-sm
                         text-ink focus:border-accent focus:outline-none">
              <option value="">All forms</option>
              {["HO3", "HO4", "AUTO", "ALL"].map((p) => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
          </div>
          <button type="submit"
            className="px-4 py-2 rounded-lg bg-accent text-paper text-sm font-semibold">
            Search
          </button>
          {(q || product) && (
            <a href="/policy" className="text-sm text-muted hover:text-accent py-2">
              Clear
            </a>
          )}
        </div>
        <p className="text-xs text-muted mt-2.5">
          Matches the words you type against the text of the form. It does not
          know what claim you are working, and it does not rank by relevance —
          the clause you need may be anywhere in the results, or absent because
          the form words it differently.
        </p>
      </form>

      <Panel title={q || product
                ? `${clauses.length} of ${total[0].n} clauses`
                : `${clauses.length} clauses`}
             sub={q
               ? `Containing “${q}”. Read them and decide which one governs.`
               : "Synthetic wording modelled on an ISO-style form. Not any insurer's actual policy."}>
        {clauses.length === 0 ? (
          <p className="text-sm text-muted py-6 text-center">
            Nothing in the wording contains “{q}”. Try the insurer's term for it
            — the form says “deterioration”, not “leaking”.
          </p>
        ) : (
          <div className="grid md:grid-cols-2 gap-3">
            {clauses.map((c) => (
              <article key={c.clause_id} className="rounded-lg border border-line p-3.5">
                <div className="flex items-baseline justify-between gap-2 mb-1.5">
                  <code className="num text-xs font-semibold text-accent">
                    {c.clause_id}
                  </code>
                  <span className={`chip !py-0 !px-1.5 capitalize ${TYPE_TONE[c.clause_type]}`}>
                    {c.clause_type}
                  </span>
                </div>
                <h3 className="text-sm font-semibold mb-1">{c.title}</h3>
                <p className="text-sm text-muted leading-relaxed">{c.body}</p>
                <p className="text-xs text-muted/70 mt-2">{c.section}</p>
              </article>
            ))}
          </div>
        )}
      </Panel>
    </Page>
  );
}
