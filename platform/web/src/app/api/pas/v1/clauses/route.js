import { ok, requireAuth } from "@/lib/api/respond";
import { logAudit } from "@/lib/api/audit";
import { query } from "@/lib/db";

// GET /api/pas/v1/clauses — the corpus retrieval ranks over.
//
// The WHOLE corpus is returned and ranking happens in the agent, not here.
// That is deliberate: keeping BM25 client-side means the gate runs with no
// database at all, and 46 clauses is nothing to ship. A corpus large enough
// to need server-side retrieval is the point at which this becomes a search
// endpoint — see DECISIONS.md.
export async function GET(req, { params }) {
  const auth = await requireAuth(req, "pas", "get_clauses");
  if (!auth.ok) return auth.response;
  const p = auth.principal;

  const url = new URL(req.url);
  const product = url.searchParams.get("product");

  const clauses = await query(
    // keywords MUST be returned. It is part of the retrieval index, and an
    // endpoint that omits it silently degrades the live path relative to the
    // offline one — which is exactly how mock and live drift apart.
    `SELECT clause_id, product, section, title, clause_type, body, perils, keywords
       FROM pas.policy_clauses
      ${product ? "WHERE product = $1 OR product = 'ALL'" : ""}
      ORDER BY clause_id`,
    product ? [product] : []
  );
  await logAudit({ adjusterId: p.adjusterId, system: "pas",
                   action: "get_clauses", resourceType: "clause",
                   decision: "allow", detail: { count: clauses.length } });
  return ok({ clauses, count: clauses.length });
}
